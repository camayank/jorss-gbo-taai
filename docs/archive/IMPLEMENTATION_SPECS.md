# Jorss-GBO Implementation Specifications

**Generated**: 2026-01-28
**Status**: Ready for Team Execution
**Total Items**: 15 specs across 3 phases

---

## Executive Summary

This document provides detailed implementation specifications for addressing the audit findings.
Each spec includes: current state analysis, specific actions, acceptance criteria, and estimated effort.

---

## Phase 1: CRITICAL Issues (Week 1-2)

### SPEC-001: Auth Stub Implementation Completion

**Priority**: CRITICAL
**Risk**: Authentication bypass
**Files**: `src/security/auth_decorators.py`

#### Current State

Lines 364-399 contain **STUB FUNCTIONS** that return `None`:
```python
def verify_jwt_token(token: str) -> Optional[dict]:
    # TODO: Implement actual JWT verification
    return None  # STUB!

def get_user_from_session(session_id: str) -> Optional[dict]:
    # TODO: Implement actual session lookup
    return None  # STUB!

def get_user_from_api_key(api_key: str) -> Optional[dict]:
    # TODO: Implement actual API key verification
    return None  # STUB!
```

#### Good News

Real implementations **DO EXIST** elsewhere:
- `src/rbac/jwt.py` - Full JWT verification
- `src/security/authentication.py` - AuthenticationManager (519 lines)
- `src/admin_panel/auth/jwt_handler.py` - Complete token handling

#### Required Actions

| # | Action | File | Details |
|---|--------|------|---------|
| 1 | Wire `verify_jwt_token()` | auth_decorators.py:364-369 | Import and call `decode_token_safe()` from `rbac/jwt.py` |
| 2 | Wire `get_user_from_session()` | auth_decorators.py:372-375 | Query sessions table via repository |
| 3 | Wire `get_user_from_api_key()` | auth_decorators.py:378-381 | Query api_keys table via repository |
| 4 | Wire `get_session_from_return_id()` | auth_decorators.py:384-387 | Query tax_returns table |
| 5 | Wire `get_tenant_for_session()` | auth_decorators.py:390-393 | Query sessions table |
| 6 | Wire `get_owner_for_session()` | auth_decorators.py:396-399 | Query sessions table |
| 7 | Add tests | tests/test_auth_decorators.py | Unit tests for all 6 functions |

#### Implementation Example

```python
# auth_decorators.py - FIXED verify_jwt_token
from rbac.jwt import decode_token_safe

def verify_jwt_token(token: str) -> Optional[dict]:
    """Verify JWT token and return user claims."""
    result = decode_token_safe(token)
    if result and result.get("valid"):
        return result.get("payload")
    return None
```

#### Acceptance Criteria

- [ ] All 6 stub functions return actual data from real implementations
- [ ] Unit tests cover success and failure cases
- [ ] Existing tests continue to pass
- [ ] No hardcoded "default" values remain

#### Estimated Effort
**1-2 days** (wiring existing code, no new logic needed)

---

### SPEC-002: JWT Secret Validation at Startup

**Priority**: CRITICAL
**Risk**: Full system compromise with default secrets
**Files**: `src/config/settings.py`, `src/web/app.py`

#### Current State: ALREADY IMPLEMENTED

The codebase **already has** production secret validation in `settings.py:198-225`:

```python
def validate_production_secrets(self) -> list:
    """Validate secrets in production environment."""
    errors = []

    # Check APP_SECRET_KEY
    if "INSECURE" in self.secret_key or self.secret_key == "change-me-in-production":
        errors.append("APP_SECRET_KEY: Must be set in production...")

    # Check JWT_SECRET
    jwt_secret = os.environ.get("JWT_SECRET")
    if not jwt_secret:
        errors.append("JWT_SECRET: Required in production...")
```

#### Required Actions

| # | Action | File | Details |
|---|--------|------|---------|
| 1 | Verify startup validation runs | app.py startup | Confirm `validate_production_secrets()` is called |
| 2 | Add blocking behavior | settings.py | Raise exception (not just warning) in production |
| 3 | Add CSRF_SECRET_KEY validation | settings.py | Currently only warns if not set |
| 4 | Document required env vars | .env.example | List all required secrets with generation commands |

#### Acceptance Criteria

- [ ] App fails to start in production if secrets are missing/weak
- [ ] App fails to start if any secret < 32 characters
- [ ] CI/CD pipeline validates .env.example has all secrets documented
- [ ] README includes secret generation commands

#### Estimated Effort
**0.5 days** (validation exists, just needs enforcement)

---

### SPEC-003: SSN Encryption Audit

**Priority**: CRITICAL
**Risk**: PII exposure, compliance violations
**Files**: `src/database/encrypted_fields.py` (584 lines)

#### Current State: WELL IMPLEMENTED

The encryption module is **production-ready** with:
- AES-256-GCM authenticated encryption
- Field-type specific key derivation (email, phone, ssn, address)
- Tenant-bound associated data
- PII validation before storage
- Audit logging for SSN access

```python
# Example from encrypted_fields.py
def encrypt_ssn(ssn: str, tenant_id: Optional[str] = None) -> str:
    """Encrypt SSN with tenant binding."""
    associated_data = tenant_id.encode() if tenant_id else None
    return encrypt_pii(ssn, field_type="ssn", associated_data=associated_data)
```

#### Required Actions

| # | Action | Scope | Details |
|---|--------|-------|---------|
| 1 | Audit SSN column usage | All 13 database files | Grep for `ssn` columns and verify they use encryption |
| 2 | Add migration validation | db_migrations.py | Ensure existing SSN data is encrypted |
| 3 | Add read-time validation | repositories | Warn if unencrypted SSN detected |
| 4 | Test key rotation | encrypted_fields.py | Verify version 2 keys can decrypt version 1 data |

#### Files to Audit

```
src/database/models.py           - Check SSN column definitions
src/database/schema.py           - Check SSN field types
src/database/persistence.py      - Check SSN save/load
src/database/etl.py              - Check SSN during import
src/database/repositories/*.py   - Check SSN in queries
src/database/alembic/versions/*  - Check SSN in migrations
```

#### Acceptance Criteria

- [ ] No plaintext SSN stored in any database column
- [ ] All SSN reads go through `decrypt_ssn()`
- [ ] All SSN writes go through `encrypt_ssn()`
- [ ] Audit log captures all SSN decryption events
- [ ] Test confirms encryption key is required in production

#### Estimated Effort
**1 day** (audit + validation, encryption already implemented)

---

### SPEC-004: CSRF Middleware Production Safety Review

**Priority**: CRITICAL
**Risk**: CSRF attacks on state-changing operations
**Files**: `src/security/middleware.py` (lines 309-476)

#### Current State: WELL IMPLEMENTED WITH CAVEATS

CSRF protection is comprehensive:
- HMAC-SHA256 signed tokens
- Constant-time comparison
- Origin/Referer validation
- Bearer auth + origin verification bypass

#### Production Concerns

| Concern | Location | Risk | Action |
|---------|----------|------|--------|
| Ephemeral secret key | app.py:136-140 | Medium | Validate CSRF_SECRET_KEY env var in production |
| 17 exempt paths | app.py:145-171 | Medium | Audit that exempt paths are read-only |
| Test bypass headers | conftest.py:54-57 | Low | Ensure test tokens rejected in production |

#### Required Actions

| # | Action | File | Details |
|---|--------|------|---------|
| 1 | Add CSRF_SECRET_KEY validation | settings.py | Require in production like JWT_SECRET |
| 2 | Audit exempt paths | middleware.py | Document why each is exempt; verify no mutations |
| 3 | Add origin allowlist validation | middleware.py | Ensure localhost origins rejected in production |
| 4 | Add CSRF metrics | middleware.py | Log token failures for monitoring |

#### Exempt Paths Requiring Audit

```python
# These paths are CSRF-exempt - verify they're safe:
/api/health                    # Read-only - OK
/api/webhook                   # Has its own signature validation?
/api/chat                      # Uses Bearer auth - OK
/api/sessions/check-active     # Read-only - OK
/api/sessions/create-session   # Creates state - VERIFY AUTH
/api/validate/fields           # Read-only - OK
/api/calculate-tax             # Read-only calculation - OK
/api/estimate                  # Read-only calculation - OK
/api/leads/create              # Creates data - NEEDS REVIEW
/api/advisor/                  # Mixed - NEEDS REVIEW
/api/ai-chat/                  # Uses Bearer auth - OK
/api/v1/auth/                  # Auth endpoints - OK
/api/v1/admin/health           # Read-only - OK
/api/v1/advisory-reports/      # Mixed - NEEDS REVIEW
/api/cpa/lead-magnet/          # Creates leads - NEEDS REVIEW
/api/lead-magnet/              # Creates leads - NEEDS REVIEW
```

#### Acceptance Criteria

- [ ] CSRF_SECRET_KEY required in production (not auto-generated)
- [ ] All exempt paths documented with justification
- [ ] Exempt paths that mutate state have alternative protection (API key, Bearer auth)
- [ ] Localhost origins rejected when APP_ENVIRONMENT=production

#### Estimated Effort
**1 day** (audit + config changes)

---

## Phase 2: HIGH Severity Issues (Weeks 2-4)

### SPEC-005: Refactor app.py into Modular Routers

**Priority**: HIGH
**Impact**: Maintainability, testability
**File**: `src/web/app.py` (6,182 lines)

#### Current State

- 114 direct route handlers in main file
- 20+ routers already included separately
- 8+ domains mixed together

#### Recommended Split

| New Router | Routes | Source Lines | Description |
|------------|--------|--------------|-------------|
| `routers/pages.py` | 24 | 1087-1465 | UI page routes |
| `routers/documents.py` | 10 | 1673-2401 | Document upload/processing |
| `routers/calculations.py` | 8 | 2693-3202 | Tax calculations |
| `routers/returns.py` | 15 | 3749-4466 | Tax return CRUD + workflow |
| `routers/analytics.py` | 10 | 4601-6101 | Tax drivers, scenarios, insights |
| `routers/exports.py` | 3 | 3391-3546 | PDF/JSON export |
| `routers/validation.py` | 3 | various | Field validation |
| `helpers/validation.py` | - | 705-799 | safe_float, validate_ssn, etc. |
| `helpers/session.py` | - | various | Session management |
| `helpers/audit.py` | - | various | Audit trail helpers |

#### Migration Steps

```bash
# Phase 1: Create new router files
mkdir -p src/web/routers src/web/helpers

# Phase 2: Extract routes (start with pages - lowest risk)
# 1. Create routers/pages.py with routes
# 2. Add to app.py: app.include_router(pages_router, tags=["pages"])
# 3. Remove old routes from app.py
# 4. Run tests

# Phase 3: Repeat for each router

# Phase 4: Extract helpers
# Move utility functions to helpers/
```

#### Acceptance Criteria

- [ ] app.py reduced to ~1,500 lines (75% reduction)
- [ ] All tests pass
- [ ] No API changes (same URLs, same responses)
- [ ] Each router has focused tests
- [ ] app.py only contains: imports, middleware, router registration, error handlers

#### Estimated Effort
**3-5 days** (incremental, low risk per step)

---

### SPEC-006: Split recommendation_helper.py

**Priority**: HIGH
**Impact**: Maintainability, SRP violation
**File**: `src/web/recommendation_helper.py` (8,288 lines)

#### Current State

35 distinct recommendation generators spanning 5 domains, all in one file.

#### Recommended Structure

```
src/web/recommendation/
├── __init__.py
├── constants.py              # Tax year constants, limits
├── models.py                 # UnifiedRecommendation, RecommendationResult
├── utils.py                  # _safe_float, _validate_profile, _create_recommendation
├── generators/
│   ├── __init__.py
│   ├── core.py               # Credits, deductions, investment (4 generators)
│   ├── retirement.py         # 401k, IRA, Roth, Medicare, SS (5 generators)
│   ├── business.py           # Entity, Rental, QBI, PAL (4 generators)
│   ├── advanced.py           # Filing status, timing, charitable, AMT, 1031 (8 generators)
│   ├── compliance.py         # Penalties, withholding, tax impact (4 generators)
│   └── intelligence.py       # Detector, CPA, strategy, smart, rules (10 generators)
├── deduplication.py          # Merge, dedupe, sort logic
├── orchestrator.py           # get_recommendations(), feature flags
└── recommendation_helper.py  # Backwards-compatible re-exports
```

#### Migration Steps

1. Create package structure
2. Move constants.py first (no dependencies)
3. Move models.py and utils.py
4. Move generators one at a time (core → retirement → business → advanced → compliance → intelligence)
5. Move deduplication.py
6. Move orchestrator.py
7. Update recommendation_helper.py to re-export everything
8. Update imports in callers

#### Acceptance Criteria

- [ ] Each module < 800 lines
- [ ] No circular imports
- [ ] All tests pass without modification
- [ ] recommendation_helper.py works as drop-in replacement (backwards compatible)
- [ ] Each generator module has focused tests

#### Estimated Effort
**3-4 days** (incremental, backwards compatible)

---

### SPEC-007: Generate OpenAPI Documentation

**Priority**: HIGH
**Impact**: Integration difficulty
**Files**: All API endpoints

#### Current State

FastAPI auto-generates OpenAPI spec, but:
- Many endpoints lack descriptions
- Request/response schemas missing
- No grouped tags

#### Required Actions

| # | Action | Details |
|---|--------|---------|
| 1 | Add docstrings to all endpoints | Include description, parameters, responses |
| 2 | Add Pydantic models for all requests | Use `response_model=` parameter |
| 3 | Add tags to group endpoints | `/api/returns/*` → tag="Tax Returns" |
| 4 | Add examples to schemas | Provide sample request/response bodies |
| 5 | Configure `/docs` and `/redoc` | Enable in production (currently may be disabled) |
| 6 | Export static OpenAPI JSON | For external API consumers |

#### Example Enhancement

```python
# Before
@app.post("/api/returns/save")
async def save_return(request: Request):
    ...

# After
@app.post(
    "/api/returns/save",
    response_model=SaveReturnResponse,
    summary="Save Tax Return",
    description="Save or update a tax return. Creates new return if no return_id provided.",
    tags=["Tax Returns"],
    responses={
        200: {"description": "Return saved successfully"},
        400: {"description": "Validation error"},
        401: {"description": "Authentication required"},
    }
)
async def save_return(
    return_data: SaveReturnRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Save a tax return with the provided data.

    - Creates new return if `return_id` is not provided
    - Updates existing return if `return_id` matches
    - Validates all tax fields before saving
    """
    ...
```

#### Acceptance Criteria

- [ ] `/docs` shows all endpoints with descriptions
- [ ] All endpoints have request/response schemas
- [ ] Endpoints grouped by logical tags
- [ ] OpenAPI spec exports without errors
- [ ] Postman collection can be generated from spec

#### Estimated Effort
**2-3 days** (documentation pass, no logic changes)

---

### SPEC-008: Create ARCHITECTURE.md

**Priority**: HIGH
**Impact**: Onboarding difficulty

#### Required Sections

```markdown
# Jorss-GBO Architecture

## 1. Overview
- System purpose (tax platform for CPAs and clients)
- High-level architecture diagram
- Key technologies (FastAPI, SQLAlchemy, Redis, Celery)

## 2. Directory Structure
- src/web/ - API and UI
- src/database/ - Models and repositories
- src/security/ - Auth, RBAC, encryption
- src/rbac/ - Role-based access control
- src/calculator/ - Tax calculation engine
- src/recommendation/ - Tax optimization recommendations

## 3. Authentication & Authorization
- JWT-based auth flow
- 8-role RBAC hierarchy
- Multi-tenant isolation

## 4. Data Flow
- Request lifecycle
- Database connections (async SQLAlchemy)
- Caching (Redis)
- Background tasks (Celery)

## 5. API Structure
- REST conventions
- Versioning strategy
- Error handling

## 6. Security Architecture
- CSRF protection
- PII encryption
- Rate limiting
- Security headers

## 7. Development Setup
- Prerequisites
- Environment variables
- Running locally
- Running tests

## 8. Deployment
- Environment configuration
- Database migrations
- Health checks
```

#### Acceptance Criteria

- [ ] New developer can understand system in < 30 minutes
- [ ] Includes architecture diagrams (Mermaid or images)
- [ ] Lists all environment variables
- [ ] Includes common troubleshooting

#### Estimated Effort
**1-2 days**

---

### SPEC-009: Resolve Outstanding TODOs

**Priority**: HIGH
**Current Count**: 85 TODOs across 40 files

#### TODO Distribution

```
Security (17 TODOs):
- src/security/auth_decorators.py: 7 (CRITICAL - addressed in SPEC-001)
- src/security/validation.py: 2
- src/security/tenant_isolation.py: 1
- src/security/encryption.py: 1

Web/API (15 TODOs):
- src/web/app.py: 2
- src/web/cpa_dashboard_pages.py: 3
- src/web/health_checks.py: 2
- src/web/admin_endpoints.py: 3
- src/web/intelligent_advisor_api.py: 1

Services (10 TODOs):
- src/services/ocr/field_extractor.py: 5
- src/services/validation_service.py: 4
- src/services/unified_tax_advisor.py: 1

Export (10 TODOs):
- src/export/pdf_generator.py: 3
- src/export/professional_formats.py: 3
- src/export/draft_form_generator.py: 2
- src/export/computation_statement.py: 1
- src/export/draft_return.py: 1

Other (33 TODOs):
- Templates, admin panel, onboarding, etc.
```

#### Triage Process

For each TODO:
1. **Delete** if no longer relevant
2. **Convert to GitHub Issue** if requires design discussion
3. **Fix immediately** if < 30 min effort
4. **Document as known limitation** if intentionally deferred

#### Acceptance Criteria

- [ ] All TODOs triaged and tracked
- [ ] Critical security TODOs fixed (auth_decorators.py)
- [ ] Remaining TODOs linked to GitHub issues
- [ ] No TODO contains sensitive information

#### Estimated Effort
**2-3 days** (triage + quick fixes)

---

## Phase 3: MEDIUM Severity Issues (Month 2-3)

### SPEC-010: Add N+1 Query Detection

**Priority**: MEDIUM
**Impact**: Performance degradation

#### Required Actions

1. Add SQLAlchemy query logging in tests
2. Install `sqla-benchmark` or custom N+1 detector
3. Add performance tests with realistic data volumes
4. Document eager loading patterns

#### Acceptance Criteria

- [ ] Tests fail if N+1 detected on critical paths
- [ ] Repository methods document loading strategy
- [ ] Performance baseline established

---

### SPEC-011: Add Integration/E2E Tests

**Priority**: MEDIUM
**Current**: 4,151 tests (mostly unit)

#### Required Actions

1. Create `tests/integration/` directory
2. Add API integration tests (real DB, real routes)
3. Add E2E tests for critical flows (login → create return → submit)
4. Add load tests with realistic data

---

### SPEC-012: Database Cascade/Index Audit

**Priority**: MEDIUM
**Risk**: Orphaned records, slow queries

#### Required Actions

1. Audit all foreign keys for proper ON DELETE behavior
2. Add missing indexes on frequently filtered columns
3. Add database constraints for data integrity

---

## Appendix A: Environment Variables

Required secrets for production:

```bash
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"

APP_SECRET_KEY=           # Main app signing (min 32 chars)
JWT_SECRET=               # JWT signing (min 32 chars)
AUTH_SECRET_KEY=          # Auth service (min 32 chars)
CSRF_SECRET_KEY=          # CSRF tokens (min 32 chars)
ENCRYPTION_MASTER_KEY=    # PII encryption (64 hex chars)
```

---

## Appendix B: Quick Wins (< 1 hour each)

| Item | Action | Impact |
|------|--------|--------|
| Secret validation | Add `raise` instead of `warning` in production | CRITICAL |
| CSRF secret | Add to startup validation | CRITICAL |
| Remove test debug | Ensure test tokens rejected in prod | HIGH |
| Health endpoint docs | Add descriptions to /api/health/* | LOW |

---

## Appendix C: Contacts

- Security issues: [security contact]
- Architecture questions: [tech lead]
- API questions: [backend team]

---

**End of Implementation Specifications**
