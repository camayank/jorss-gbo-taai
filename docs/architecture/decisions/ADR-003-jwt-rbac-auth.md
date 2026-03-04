# ADR-003: JWT + RBAC Authentication Model

## Status
Accepted

## Context
The platform has multiple user types (consumers, CPA staff, CPA admins, platform admins) with different permission levels. We needed an authentication model that supports:
- Stateless API authentication
- Role-based access control
- Multi-tenant context per request
- Token refresh without re-login

## Decision
JWT access tokens (1hr) + refresh tokens (7-30 days) with RBAC claims embedded in the JWT payload.

## Rationale
- Stateless: no session store needed for token validation
- Self-contained: role and tenant claims travel with the token
- Standard: broad library and tooling support
- Scalable: no shared session state between workers

## Consequences
- Token revocation requires a blacklist (Redis-backed in production)
- Token size is larger than session IDs
- Secret rotation requires careful coordination
- Two auth systems coexist: admin panel (`src/admin_panel/api/auth_routes.py`) and core (`src/core/api/auth_routes.py`)

## Token Structure
```json
{
  "sub": "user_id",
  "type": "access|refresh",
  "role": "consumer|cpa_staff|cpa_admin|platform_admin",
  "tenant_id": "firm_uuid",
  "exp": "unix_timestamp"
}
```

## References
- `src/admin_panel/auth/jwt_handler.py` — JWT creation and validation
- `src/admin_panel/auth/rbac.py` — Role-based access control
- `src/core/services/auth_service.py` — Core auth service
