# Full Bug Remediation Plan

**Date:** 2026-03-25
**Scope:** All 51 bugs identified in comprehensive code review
**Strategy:** Fix by severity tier, grouped by file/module per commit
**Delivery:** ~15 commits, one per file/module group

---

## Commit Groups (ordered by highest severity in each group)

### Commit 1: `src/web/routers/returns.py` — IDOR + cross-tenant fixes
**Severity:** Critical #1 + High #9, #10
**Effort:** Medium (~30 min)
**Bugs:**
- #1 CRITICAL: Add ownership check to GET/DELETE `/{return_id}` — verify `auth.user_id` owns the return
- #9 HIGH: Add user/firm scoping to `list_returns()` — pass `user_id` filter to persistence layer
- #10 HIGH: Add role + ownership check to `revert-to-draft` endpoint

### Commit 2: `src/resilience/retry.py` + `circuit_breaker.py` — async safety
**Severity:** Critical #2 + High #18
**Effort:** Small (~15 min)
**Bugs:**
- #2 CRITICAL: Change bare `raise` to `raise exception` in `handle_exception()` line 351
- #18 HIGH: Replace `threading.Lock` with async-aware locking in circuit breaker's async wrapper

### Commit 3: `src/database/transaction.py` — double-commit guard
**Severity:** Critical #3
**Effort:** Tiny (~5 min)
**Bugs:**
- #3 CRITICAL: Add `self._is_active = False` after successful commit

### Commit 4: `src/calculator/decimal_math.py` + `src/models/tax_return.py` — financial precision
**Severity:** Critical #4 + Medium #33, #35
**Effort:** Medium (~30 min)
**Bugs:**
- #4 CRITICAL: Handle open-ended top bracket in `calculate_progressive_tax` — add explicit top-bracket handling for income exceeding last threshold
- #33 MEDIUM: Replace `* 0.20` float in tax_return.py with `decimal_math.multiply()`
- #35 MEDIUM: Keep SE tax results as Decimal, only convert at API boundary

### Commit 5: `src/domain/event_bus.py` — event store correctness
**Severity:** Critical #5 + High #21, #11-perf + Medium #44
**Effort:** Large (~45 min)
**Bugs:**
- #5 CRITICAL: Make version read + insert atomic (use `BEGIN IMMEDIATE`), add UNIQUE constraint on `(stream_id, version)`
- #21 HIGH: Use `model.model_dump(mode='json')` for nested UUID/datetime serialization
- #11-perf HIGH: Reuse SQLite connection instead of opening new one per event
- #44 MEDIUM: Add critical handler failure tracking — at minimum log at ERROR and surface in return value

### Commit 6: `migrations/` + `scripts/migrate_sqlite_to_postgres.py` — migration safety
**Severity:** Critical #6, #7 + High #29 + Medium #42
**Effort:** Medium (~30 min)
**Bugs:**
- #6 CRITICAL: Add `_SAFE_SQL_IDENT` regex validation for table names in sqlite-to-postgres migration
- #7 CRITICAL: Call `conn.rollback()` before recording failure in `run_migration.py`
- #29 HIGH: Add `table_exists()` guard before each index creation block in `add_performance_indexes.py`
- #42 MEDIUM: Change `get_pending_migrations` to look for `.py` files (not `.sql`)

### Commit 7: `src/web/templates/auth/` — frontend auth security
**Severity:** Critical #8 + Medium #39 + BUG-16 (OAuth JWT in URL)
**Effort:** Medium (~25 min)
**Bugs:**
- #8 CRITICAL: Validate `next` parameter is same-origin relative path before redirect
- #39 MEDIUM: Document JWT-in-URL risk, add TODO for code exchange pattern
- BUG-16 MEDIUM: Same as #39 — applies to both login.html and signup.html

### Commit 8: `src/security/safe_xml.py` + `data_sanitizer.py` — security hardening
**Severity:** High #11, #15 + Medium #34, #36
**Effort:** Medium (~30 min)
**Bugs:**
- #11 HIGH: Refuse to parse XML if `defusedxml` not installed (remove bypassable fallback)
- #15 HIGH: Tighten routing/account regex patterns to require context labels
- #34 MEDIUM: Replace substring sensitive field check with word-boundary matching (split on `_`)
- #36 MEDIUM: Handle StringIO path correctly — use `ET.fromstring(content)` instead of `ET.parse(source)`

### Commit 9: `src/rbac/jwt.py` + `src/admin_panel/auth/jwt_handler.py` + `auth_routes.py` — auth fixes
**Severity:** High #12, #13 + Low #49
**Effort:** Small (~20 min)
**Bugs:**
- #12 HIGH: Use `datetime.fromtimestamp(exp, tz=timezone.utc)` everywhere
- #13 HIGH: Reset `failed_login_attempts = 0` and `locked_until = NULL` on successful admin login
- #49 LOW: Increase MFA backup code entropy to `secrets.token_hex(8)` (64 bits)

### Commit 10: `src/web/rate_limiter.py` + `src/web/middleware.py` — request handling
**Severity:** High #14 + Low #47
**Effort:** Small (~15 min)
**Bugs:**
- #14 HIGH: Only trust X-Forwarded-For when behind known proxy (add `TRUSTED_PROXIES` config)
- #47 LOW: Replace timestamp-based request ID with `uuid.uuid4()`

### Commit 11: `src/rules/rule_engine.py` + `src/services/async_tax_return_service.py` — runtime safety
**Severity:** High #16, #17 + Medium #37
**Effort:** Small (~20 min)
**Bugs:**
- #16 HIGH: Replace unbounded dict cache with `functools.lru_cache(maxsize=1024)` or `cachetools.LRUCache`
- #17 HIGH: Use `field(default_factory=list)` for `errors` and `warnings` in `CalculationResult`
- #37 MEDIUM: Log state tax errors at ERROR level and append to `CalculationResult.warnings`

### Commit 12: `src/webhooks/service.py` — webhook fixes
**Severity:** High #19, #20
**Effort:** Small (~15 min)
**Bugs:**
- #19 HIGH: Make `retry_delivery` async, or use `asyncio.create_task()` / `loop.run_until_complete()` to properly await `queue_event`
- #20 HIGH: Move `_records = []` to `__init__` as `self._records = []`

### Commit 13: `src/validation/dependent_validator.py` + `src/export/data_importer.py` — tax logic
**Severity:** High #22, #23, #25 + Medium #43, #15-validator
**Effort:** Large (~45 min)
**Bugs:**
- #22 HIGH: Fix equal-AGI tiebreaker — neither parent wins automatically, require consent flag
- #23 HIGH: Replace `is_claimed_by_another` with proper "not anyone's QC" determination per Pub 501
- #25 HIGH: Sum both `cap_loss` and `net_cap_gain` carryover sources when both present
- #43 MEDIUM: Process all elements in multi-return JSON arrays (loop instead of `data[0]`)
- #15-validator MEDIUM: Add note/warning for tax years beyond 2025 where limits may differ

### Commit 14: `src/web/static/js/` — frontend JS fixes
**Severity:** High #26, #27 + Medium #41, #45 + Low #48 + frontend XSS bugs
**Effort:** Large (~45 min)
**Bugs:**
- #26 HIGH: Clear `timeoutId` before recursive retry in api.js
- #27 HIGH: Use `escapeHtml()` in `updateInsights`/`updateStats` in advisor-display.js
- #41 MEDIUM: Replace `fetch()` with `secureFetch()` in consent POST (advisor-core.js)
- #45 MEDIUM: Escape `missingFields` and `completionHint` before innerHTML
- #48 LOW: Fix Unicode escapes — add backslashes (`'\u2600\uFE0F'`)
- BUG-08 HIGH: Escape nudge config fields or use textContent
- BUG-13 MEDIUM: Escape `item.value`/`item.field` in quick edit panel

### Commit 15: Remaining medium/low fixes
**Severity:** Medium #30, #31, #32, #38, #40 + High #28 + Low #50, #51
**Effort:** Medium (~30 min)
**Bugs:**
- #30 MEDIUM: Add ownership verification to GDPR erasure endpoint
- #31 MEDIUM: Sanitize `identifier_value` — allow only `[a-zA-Z0-9-]` before glob use
- #32 MEDIUM: Call `validate_upload()` (magic-byte check) in `upload_routes.py`
- #38 MEDIUM: Consolidate impersonation session stores to single source of truth
- #40 MEDIUM: Add CSRF token to support form (create.html)
- #28 HIGH: Rewrite recommendation tests to test runtime behavior, not source text
- #46 MEDIUM: Narrow `conftest.py` except to `ModuleNotFoundError` only
- #50 LOW: Add Nginx healthcheck to docker-compose.production.yml
- #51 LOW: Replace `require()` with ESM `import` in vite.build.config.js
- #24 HIGH: Use different seeds for synthetic data generation vs train/test split
- #14-tfidf MEDIUM: Use `/` instead of `//` for per-item timing in tfidf_classifier.py

---

## Summary

| Tier | Count | Commits touching |
|------|-------|-----------------|
| Critical | 8 | Commits 1-7 |
| High | 21 | Commits 1-15 |
| Medium | 17 | Commits 4-15 |
| Low | 5 | Commits 9-10, 14-15 |
| **Total** | **51** | **15 commits** |

## Execution Order

Commits 1-7 first (all Critical bugs resolved).
Then commits 8-12 (High-severity dominant groups).
Then commits 13-15 (remaining High + Medium + Low).

## Risk Notes

- **Commit 1** (returns.py IDOR) may require persistence layer changes — verify `list_returns` and `load_return` accept a `user_id` parameter
- **Commit 5** (event_bus.py) is the most complex — touches event sourcing internals, test thoroughly
- **Commit 13** (dependent validator) involves IRS tax law logic — verify against Pub 501 tiebreaker rules
- **Commit 14** (frontend JS) has many small changes — test each UI component after fixes
