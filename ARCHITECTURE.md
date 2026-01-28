# Jorss-GBO Architecture

> Tax Preparation Platform for CPAs and Clients

## 1. Overview

Jorss-GBO is a comprehensive tax preparation platform that serves both CPAs and individual taxpayers. It provides intelligent tax optimization, document processing, and multi-tenant support for accounting firms.

### Key Technologies

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL / SQLite |
| Async ORM | SQLAlchemy 2.0 (async) |
| Cache | Redis |
| Task Queue | Celery |
| Authentication | JWT + Session-based |
| Encryption | AES-256-GCM for PII |

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│  Web UI     │  CPA Portal │ Client App  │ Admin Panel │  API    │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                          │
├─────────────────────────────────────────────────────────────────┤
│  Security Middleware │ RBAC │ Rate Limiting │ CSRF Protection   │
├─────────────────────────────────────────────────────────────────┤
│           Routers (Documents, Returns, Calculations, etc.)       │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Tax Engine   │    │   OCR/AI      │    │ Recommendation│
│  Calculator   │    │   Services    │    │   Engine      │
└───────────────┘    └───────────────┘    └───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                  │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│  PostgreSQL │   Redis     │   Celery    │  File Store │  Audit  │
│  (Primary)  │   (Cache)   │  (Tasks)    │  (Docs)     │  (Logs) │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────┘
```

## 2. Directory Structure

```
src/
├── web/                    # API and UI (FastAPI)
│   ├── app.py              # Main application entry
│   ├── routers/            # Modular route handlers
│   │   ├── pages.py        # HTML page routes
│   │   ├── documents.py    # Document upload/management
│   │   ├── returns.py      # Tax return CRUD
│   │   ├── calculations.py # Tax calculations
│   │   ├── validation.py   # Field validation
│   │   ├── scenarios.py    # What-if analysis
│   │   └── health.py       # Health checks
│   ├── recommendation/     # Tax optimization engine
│   │   ├── models.py       # Data models
│   │   ├── constants.py    # Tax year constants
│   │   ├── utils.py        # Helper functions
│   │   ├── orchestrator.py # Main entry point
│   │   └── generators/     # Recommendation generators
│   └── helpers/            # Shared utilities
│
├── database/               # Data persistence
│   ├── models.py           # SQLAlchemy ORM models
│   ├── repositories/       # Data access layer
│   ├── session_persistence.py  # Session storage
│   ├── encrypted_fields.py # PII encryption
│   └── alembic/            # Database migrations
│
├── security/               # Security components
│   ├── auth_decorators.py  # Authentication decorators
│   ├── authentication.py   # Auth manager
│   ├── middleware.py       # Security middleware
│   └── encryption.py       # Encryption utilities
│
├── rbac/                   # Role-Based Access Control
│   ├── jwt.py              # JWT token handling
│   ├── permissions.py      # Permission definitions
│   └── roles.py            # Role hierarchy
│
├── calculator/             # Tax calculation engine
│   ├── tax_calculator.py   # Core calculations
│   ├── recommendations.py  # Legacy recommendations
│   └── brackets.py         # Tax brackets
│
├── services/               # Business services
│   ├── ocr/                # Document OCR
│   ├── validation/         # Business validation
│   └── ai/                 # AI/ML services
│
├── config/                 # Configuration
│   ├── settings.py         # Application settings
│   └── database.py         # Database configuration
│
├── audit/                  # Audit trail
│   └── audit_trail.py      # Audit logging
│
└── admin_panel/            # Admin UI
    └── auth/               # Admin authentication
```

## 3. Authentication & Authorization

### Authentication Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client  │────▶│  Login   │────▶│  Verify  │────▶│  Issue   │
│          │     │ Request  │     │  Creds   │     │   JWT    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                         │
                                                         ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Resource │◀────│  RBAC    │◀────│  Decode  │◀────│  Bearer  │
│ Access   │     │  Check   │     │   JWT    │     │  Token   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### JWT Token Structure

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "name": "User Name",
  "role": "cpa_admin",
  "user_type": "cpa",
  "firm_id": "uuid",
  "firm_name": "Firm Name",
  "exp": 1234567890,
  "type": "access"
}
```

### 8-Role RBAC Hierarchy

| Level | Role | Description |
|-------|------|-------------|
| 0 | `system_admin` | Full system access |
| 1 | `partner_admin` | White-label partner management |
| 2 | `firm_owner` | Firm-level full access |
| 2 | `cpa_admin` | CPA with admin privileges |
| 3 | `cpa_staff` | Standard CPA user |
| 3 | `cpa_viewer` | Read-only CPA access |
| 4 | `client` | Client portal access |
| 4 | `taxpayer` | Anonymous/self-service |

### Multi-Tenant Isolation

```
┌─────────────────────────────────────────────┐
│                 Request                      │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│        Extract tenant_id from JWT           │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│  Apply tenant filter to all DB queries      │
│  WHERE tenant_id = :current_tenant          │
└─────────────────────────────────────────────┘
```

## 4. Data Flow

### Request Lifecycle

```
1. Request arrives
   │
2. Security Middleware
   ├── Security Headers (HSTS, CSP, X-Frame-Options)
   ├── Rate Limiting (60 req/min per IP)
   ├── Request Validation (size, content-type)
   └── CSRF Protection (state-changing ops)
   │
3. Authentication
   ├── JWT Token Verification
   ├── Session Validation
   └── API Key Check
   │
4. Authorization (RBAC)
   ├── Permission Check
   ├── Hierarchy Level Check
   └── Resource Access Check
   │
5. Route Handler
   ├── Input Validation (Pydantic)
   ├── Business Logic
   └── Audit Logging
   │
6. Repository Layer
   ├── Tenant Isolation
   ├── PII Encryption/Decryption
   └── Database Operations
   │
7. Response
   ├── Sanitize PII
   ├── Add Security Headers
   └── Return JSON/HTML
```

### Database Connections

```python
# Async SQLAlchemy Session
async with async_session() as session:
    async with session.begin():
        result = await repository.get(entity_id)
```

## 5. API Structure

### REST Conventions

| Method | Path | Action |
|--------|------|--------|
| GET | `/api/returns` | List returns |
| GET | `/api/returns/{id}` | Get return |
| POST | `/api/returns/save` | Create/update return |
| DELETE | `/api/returns/{id}` | Delete return |
| POST | `/api/returns/{id}/submit` | Submit for review |

### Versioning

- `/api/v1/*` - Versioned API endpoints
- `/api/*` - Legacy/unversioned endpoints

### Error Handling

```json
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "message": "User-friendly message",
  "details": {
    "field": "ssn",
    "error": "Invalid format"
  }
}
```

## 6. Security Architecture

### CSRF Protection

- HMAC-SHA256 signed tokens
- Constant-time comparison
- Exempt paths documented with justification
- Bearer auth + origin verification bypass

### PII Encryption

```python
# Encrypt SSN before storage
encrypted = encrypt_ssn(ssn, tenant_id)

# Decrypt for display
plaintext = decrypt_ssn(encrypted, tenant_id)

# Always mask for logs
masked = mask_ssn(ssn)  # ***-**-1234
```

### Rate Limiting

| Resource | Limit |
|----------|-------|
| API (general) | 60 req/min |
| Login attempts | 5/min per IP |
| Document upload | 10/min |
| Password reset | 3/hour |

### Security Headers

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
```

## 7. Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or SQLite for dev)
- Redis 7+
- Node.js 18+ (for frontend)

### Environment Variables

```bash
# Required for Production
APP_SECRET_KEY=           # Min 32 chars
JWT_SECRET=               # Min 32 chars
AUTH_SECRET_KEY=          # Min 32 chars
PASSWORD_SALT=            # Min 16 chars
ENCRYPTION_MASTER_KEY=    # Min 32 chars
CSRF_SECRET_KEY=          # Min 32 chars

# Generate with:
python -c "import secrets; print(secrets.token_hex(32))"

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/jorss_gbo

# Redis
REDIS_URL=redis://localhost:6379/0

# Environment
APP_ENVIRONMENT=development  # or production
```

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the server
uvicorn src.web.app:app --reload --host 0.0.0.0 --port 8000

# Start Celery worker (separate terminal)
celery -A tasks.celery_app worker --loglevel=info
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_auth_decorators.py -v
```

## 8. Deployment

### Environment Configuration

| Environment | APP_ENVIRONMENT | Features |
|-------------|-----------------|----------|
| Development | `development` | Debug mode, auto-reload |
| Staging | `staging` | Production security, test data |
| Production | `production` | Full security enforcement |

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Health Checks

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic health check |
| `/api/health` | Detailed health status |
| `/api/health/database` | Database connectivity |
| `/api/health/cache` | Redis connectivity |
| `/api/health/resilience` | Circuit breaker status |

### Monitoring

- Application logs: `logs/app.log`
- Audit logs: `logs/audit.log`
- Security logs: `logs/security.log`

## 9. Common Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Test connection
psql -h localhost -U postgres -d jorss_gbo
```

### Redis Connection Issues

```bash
# Check Redis is running
redis-cli ping

# Clear cache
redis-cli FLUSHDB
```

### Authentication Issues

1. Verify JWT_SECRET is set correctly
2. Check token expiration
3. Verify user exists and is active
4. Check RBAC permissions

### Migration Issues

```bash
# Check current revision
alembic current

# Show migration history
alembic history

# Generate SQL without applying
alembic upgrade head --sql
```

## 10. Architecture Decisions

### Why FastAPI?

- Native async support for high concurrency
- Automatic OpenAPI documentation
- Pydantic validation built-in
- Modern Python typing

### Why SQLAlchemy 2.0 Async?

- Async/await support for non-blocking I/O
- Mature ORM with excellent documentation
- Type hints support
- Unit of Work pattern

### Why Redis for Caching?

- Sub-millisecond latency
- Pub/sub for real-time features
- Session storage
- Rate limiting support

### Why Celery for Background Tasks?

- Reliable task execution
- Retry mechanisms
- Task monitoring
- Scalable workers

---

*Last updated: January 2026*
