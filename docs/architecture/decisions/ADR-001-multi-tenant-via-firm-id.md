# ADR-001: Multi-Tenant Isolation via firm_id

## Status
Accepted

## Context
The platform serves multiple CPA firms, each with their own clients, tax returns, and recommendations. We needed to choose between:
1. Schema-per-tenant (separate database schemas)
2. Database-per-tenant (separate databases)
3. Row-level isolation via tenant identifier column

## Decision
We use **row-level isolation** with `firm_id` (and legacy `tenant_id`) columns on all tenant-scoped tables.

## Rationale
- Simpler operations: single database, single schema, standard migrations
- Lower cost: no per-tenant database provisioning needed
- Easier querying across tenants for platform analytics
- Neon free tier supports this pattern well

## Consequences
- Every query on tenant-scoped tables MUST include `WHERE firm_id = ?` (or `tenant_id`)
- API middleware extracts tenant context and passes it through the request chain
- Cross-tenant data leakage is the primary security risk — all data routes enforce tenant filtering
- A mapping table (`tenant_firm_mapping`) bridges legacy `tenant_id` to `firm_id`

## References
- `src/cpa_panel/api/data_routes.py` — tenant filter pattern
- `src/database/repositories/` — repository layer with tenant scoping
- `alembic/versions/` — migration adding firm_id columns
