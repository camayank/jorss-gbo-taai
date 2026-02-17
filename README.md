# Jorss GBO - AI-Powered Tax Preparation Platform

A production-grade, multi-tenant SaaS platform for US federal and state tax preparation. Features 49+ IRS form models, AI-powered advisory, white-label CPA portals, and enterprise admin capabilities.

[![Tests](https://img.shields.io/badge/tests-4100%2B%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![Tax Year](https://img.shields.io/badge/tax%20year-2025-orange)]()
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688)]()

## Platform Overview

The platform serves three distinct user portals:

| Portal | Audience | Key Capabilities |
|--------|----------|------------------|
| **Web Portal** | End users / taxpayers | Guided filing, AI chat, document upload, Express Lane |
| **CPA Panel** | Tax professionals / firms | White-label branding, client management, practice analytics |
| **Admin Panel** | Platform operators | Tenant management, system monitoring, API key management |

## Core Capabilities

### Tax Calculation Engine
- **49+ IRS form models** with full computation logic
- **Progressive federal brackets** for all filing statuses (Single, MFJ, MFS, HOH, QSS)
- **All 50 states + DC** with state-specific rules, surtaxes, and local taxes
- **Decimal-precise arithmetic** using Python `Decimal` with IRS-standard rounding
- **QBI deduction** (Form 8995), **AMT** (Form 6251), **estimated tax penalty** (Form 2210)

### Supported IRS Forms

| Category | Forms |
|----------|-------|
| **Core** | Form 1040, Form 1040-X (Amended) |
| **Schedules** | A (Itemized), B (Interest/Dividends), C (Business), D (Capital Gains), E (Rental/K-1), F (Farm), H (Household Employment) |
| **Income** | 8949 (Capital Assets), 6781 (Section 1256), 8814 (Parent's Election) |
| **Retirement** | 8606 (Nondeductible IRAs), 5329 (Penalties), 8889 (HSA) |
| **Credits** | 8801 (Prior Year AMT), 1116 (Foreign Tax), 8863 (Education) |
| **International** | 2555 (Foreign Earned Income), 5471 (Foreign Corp) |
| **Real Estate** | 4797 (Business Property), 6252 (Installment Sales), 8582 (Passive Loss), 8829 (Home Office) |
| **Investment** | 4952 (Investment Interest), 8615 (Kiddie Tax) |
| **Business** | 3115 (Accounting Method), 4562 (Depreciation), 8995 (QBI) |

### AI & Machine Learning
- **GPT-4 conversational agent** for guided tax data collection
- **AI advisory reports** with tax-saving recommendations
- **TF-IDF document classifiers** for W-2/1099 categorization
- **OCR pipeline** (Tesseract + AI-enhanced) for document parsing
- **Smart Tax engine** with complexity routing and deduction detection

### CPA White-Label Portal
- Custom branding (logo, colors, domain)
- Client management and engagement tracking
- Practice analytics and deadline monitoring
- Staff management with role-based permissions
- Subscription tiers ($20K/yr enterprise pricing)

### Security
- JWT authentication with RBAC (role-based access control)
- HMAC-SHA256 SSN hashing with secret key management
- AES-256 PII field encryption
- CSRF protection, CSP headers, rate limiting
- Tenant isolation with per-firm database boundaries
- Audit trail with HMAC integrity verification

## Quick Start

### Requirements
- Python 3.11+
- PostgreSQL 14+ (primary database)
- Redis 7+ (caching and sessions)

### Setup

```bash
# Clone the repository
git clone https://github.com/camayank/jorss-gbo-taai.git
cd jorss-gbo-taai

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@localhost:5432/jorss_gbo
REDIS_URL=redis://localhost:6379/0
APP_SECRET_KEY=<generate-with-secrets.token_hex(32)>

# Required in production
APP_ENVIRONMENT=production
SSN_HASH_SECRET=<generate-with-secrets.token_hex(32)>
AUDIT_HMAC_KEY=<generate-with-secrets.token_hex(32)>

# Optional (for AI features)
OPENAI_API_KEY=your_openai_api_key
```

### Launch Bootstrap (Recommended)

```bash
# 1) Generate secure secrets + scaffold missing launch vars in .env
python scripts/setup_launch_env.py --environment production

# 2) Fill unresolved values in .env:
#    - DATABASE_URL
#    - OPENAI_API_KEY

# 3) Run preflight checks before launch
python scripts/preflight_launch.py --mode production

# 4) Run migrations
python -m alembic -c alembic.ini upgrade head
```

### Run

```bash
# Web server (FastAPI + Uvicorn)
python run_web.py
# Open http://127.0.0.1:8000

# CLI interactive agent
python run.py
```

## Project Structure

```
jorss-gbo-taai/
├── src/
│   ├── main.py                    # FastAPI app factory
│   │
│   ├── models/                    # Data models (49+ IRS forms)
│   │   ├── taxpayer.py            # TaxpayerInfo, FilingStatus, Dependent
│   │   ├── income.py              # W2, 1099 forms, income sources
│   │   ├── deductions.py          # Standard / itemized deductions
│   │   ├── credits.py             # All tax credit models
│   │   ├── tax_return.py          # TaxReturn container
│   │   ├── schedule_*.py          # Schedule A-H models
│   │   └── form_*.py              # IRS form models
│   │
│   ├── calculator/                # Tax calculation engines
│   │   ├── engine.py              # Federal tax engine
│   │   ├── decimal_math.py        # IRS-standard rounding utilities
│   │   ├── tax_year_config.py     # 2025 brackets, rates, limits
│   │   ├── qbi_calculator.py      # Qualified Business Income
│   │   └── state/                 # State tax calculators (50 + DC)
│   │
│   ├── web/                       # Web API layer
│   │   ├── app.py                 # FastAPI application setup
│   │   ├── routers/               # API route modules
│   │   ├── ai_chat_api.py         # AI conversational endpoints
│   │   ├── express_lane_api.py    # Express Lane filing API
│   │   ├── smart_tax_api.py       # Smart tax analysis API
│   │   ├── advisory_api.py        # Advisory report endpoints
│   │   ├── templates/             # Jinja2 HTML templates
│   │   └── static/                # CSS, JS, images
│   │
│   ├── admin_panel/               # Platform admin portal
│   │   ├── api/                   # Admin REST endpoints
│   │   ├── auth/                  # Admin authentication
│   │   ├── models/                # Admin data models
│   │   ├── services/              # Admin business logic
│   │   └── support/               # Support ticket system
│   │
│   ├── cpa_panel/                 # CPA white-label portal
│   │   ├── api/                   # CPA REST endpoints
│   │   ├── analysis/              # Practice analytics
│   │   ├── engagement/            # Client engagement tracking
│   │   ├── lead_state/            # Lead/prospect management
│   │   ├── notifications/         # CPA notification system
│   │   ├── payments/              # Payment processing
│   │   ├── pricing/               # Subscription tiers
│   │   ├── security/              # CPA-specific security
│   │   └── workflow/              # Review workflow engine
│   │
│   ├── agent/                     # AI conversational agent
│   ├── smart_tax/                 # Smart tax analysis engine
│   │   ├── orchestrator.py        # Multi-step analysis orchestrator
│   │   ├── complexity_router.py   # Filing complexity assessment
│   │   ├── deduction_detector.py  # Missed deduction detection
│   │   └── document_processor.py  # Document analysis pipeline
│   │
│   ├── advisory/                  # AI advisory report generation
│   ├── recommendation/            # Rules-based tax recommendations
│   ├── projection/                # Multi-year tax projections
│   │
│   ├── database/                  # Data persistence layer
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   ├── persistence.py         # CRUD operations
│   │   ├── repositories/          # Repository pattern
│   │   ├── encrypted_fields.py    # AES-256 PII encryption
│   │   └── tenant_models.py       # Multi-tenant models
│   │
│   ├── security/                  # Security infrastructure
│   │   └── ssn_hash.py            # HMAC-SHA256 SSN hashing
│   │
│   ├── rbac/                      # Role-based access control
│   │   ├── jwt.py                 # JWT token management
│   │   ├── roles.py               # Role definitions
│   │   ├── permissions.py         # Permission matrix
│   │   └── decorators.py          # @require_role, @require_perm
│   │
│   ├── audit/                     # Audit trail system
│   │   └── unified/               # HMAC-verified audit logging
│   │
│   ├── realtime/                  # Real-time updates
│   │   ├── connection_manager.py  # WebSocket connection pool
│   │   ├── websocket_routes.py    # WS endpoints
│   │   └── events.py              # Event types and publishing
│   │
│   ├── export/                    # Report generation
│   │   ├── pdf_generator.py       # PDF tax returns
│   │   ├── computation_statement.py # IRS computation statements
│   │   └── professional_formats.py # CPA-branded exports
│   │
│   ├── ml/                        # Machine learning models
│   │   ├── classifiers/           # Document classifiers
│   │   └── training/              # Model training pipelines
│   │
│   ├── parser/                    # Document parsing (OCR)
│   ├── validation/                # Input validation rules
│   ├── middleware/                 # HTTP middleware
│   ├── cache/                     # Redis caching layer
│   ├── tasks/                     # Celery background tasks
│   ├── webhooks/                  # Outbound webhook system
│   ├── notifications/             # Email/SMS notifications
│   ├── subscription/              # SaaS subscription management
│   ├── onboarding/                # User onboarding flows
│   ├── universal_report/          # Branded report engine
│   ├── services/                  # Shared business services
│   ├── resilience/                # Circuit breaker, retries
│   ├── config/                    # Configuration management
│   ├── core/                      # Core domain models
│   ├── domain/                    # Domain events (CQRS)
│   ├── rules/                     # Tax rule definitions
│   └── utils/                     # Shared utilities
│
├── tests/                         # Test suite (4100+ tests)
│   ├── test_*.py                  # Unit and integration tests
│   ├── admin_panel/               # Admin panel tests
│   ├── security/                  # Security audit tests
│   ├── integration/               # End-to-end tests
│   └── performance/               # Load and performance tests
│
├── migrations/                    # Alembic database migrations
├── scripts/                       # Operational scripts
│   ├── seed_demo_data.py          # Demo data seeding
│   ├── migrate_encrypt_pii.py     # PII encryption migration
│   └── setup_platform_admin.py    # Initial admin setup
│
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md            # Platform architecture diagram
│   ├── API.md                     # API reference
│   ├── DEPLOYMENT_GUIDE.md        # Deployment instructions
│   ├── SECURITY.md                # Security overview
│   └── USAGE.md                   # Usage guide
│
├── docker-compose.yml             # Container orchestration
├── Dockerfile                     # Container build
├── pyproject.toml                 # Python project metadata
├── requirements.txt               # Python dependencies
├── run.py                         # CLI entry point
└── run_web.py                     # Web server entry point
```

## Testing

```bash
# Run all tests
PYTHONPATH=".:src" pytest tests/ -v

# Run specific test module
PYTHONPATH=".:src" pytest tests/test_brackets.py -v

# Run with coverage
PYTHONPATH=".:src" pytest tests/ --cov=src --cov-report=html

# Run security audit tests
PYTHONPATH=".:src" pytest tests/security/ -v
```

## Deployment

See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) for full deployment instructions.

```bash
# Docker deployment
docker-compose up -d

# Environment setup
export APP_ENVIRONMENT=production
export DATABASE_URL=postgresql://...
export SSN_HASH_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
export AUDIT_HMAC_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full platform architecture diagram covering all modules, data flows, and infrastructure.

## Disclaimers

> **This is a development/educational tool.**

- Review all calculations carefully before filing
- Consult a qualified tax professional for complex situations
- Tax laws change annually - verify current IRS rules
- Not affiliated with or endorsed by the IRS

## License

MIT License - See [LICENSE](LICENSE) for details.
