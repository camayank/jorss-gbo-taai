# Go-Live Readiness — Consolidated Issues & Remediation Plan

**Date:** 2026-03-18
**Status:** Pre-Go-Live Audit Complete
**Platform:** JORSS-GBO Tax Advisory Platform (B2B SaaS for CPA Firms)

---

## Table of Contents

1. [Summary Dashboard](#summary-dashboard)
2. [Phase 0 — Foundation Fixes (3 items)](#phase-0--foundation-fixes)
3. [Phase 1 — Go-Live Blockers (18 items)](#phase-1--go-live-blockers)
4. [Phase 2 — High Severity (19 items)](#phase-2--high-severity)
5. [Phase 3 — Medium Severity (22 items)](#phase-3--medium-severity)
6. [Phase 4 — Enhancement Spec (9 items)](#phase-4--enhancement-spec)
7. [Phase 5 — Product PRDs (6 items)](#phase-5--product-prds)
8. [Implementation Order](#implementation-order)

---

## Summary Dashboard

| Role | Blockers | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| **QA Lead** | 3 | 7 | 4 | 3 | 17 |
| **Security Engineer** | 1 | 3 | 5 | 2 | 11 |
| **DevOps/Infra** | 0 | 4 | 9 | 3 | 16 |
| **Legal/Compliance** | 5 | 4 | 2 | 1 | 12 |
| **Product Manager** | 0 | 3 | 3 | 0 | 6 |
| **Architect (Mismatches)** | 3 | 4 | 3 | 0 | 10 |
| **Enhancement Spec** | — | — | — | — | 9 |
| **Totals** | **12** | **25** | **26** | **9** | **81** |

> After deduplication (several findings overlap across roles), the actionable item count is **~62 unique issues**.

---

## Phase 0 — Foundation Fixes

These must be completed before any new features or enhancements.

### F0-A: Schema Bridge for Lead Magnet Templates
- **Source:** Architect audit — Critical mismatch #1
- **Problem:** Lead magnet templates (`tier1_report.html`, `tier2_analysis.html`) expect `tax_health_score`, `insights[].teaser_description`, `savings_range`, `locked_count` — none exist on `StrategyRecommendation`. Templates render demo/hardcoded data.
- **Fix:** Create `src/web/helpers/lead_magnet_report_builder.py` that transforms `AdvisoryReportResult` → lead magnet template schema.
- **Files:** `src/web/helpers/lead_magnet_report_builder.py` (new), `src/web/routes/page_routes.py`

### F0-B: PDF Tier Enforcement
- **Source:** Architect audit — Critical mismatch #2; Security Finding #2
- **Problem:** `tier_control.py` sets `pdf_download=False` for FREE tier, but `report_routes.py` never checks tier. All users get full PDFs.
- **Fix:** Add tier check as FastAPI dependency on all PDF endpoints (`/report/{session_id}/pdf`, `/universal-report/{session_id}/pdf`).
- **Files:** `src/web/advisor/report_routes.py`, `src/subscription/tier_control.py`

### F0-C: Unified Gating Model
- **Source:** Architect audit — Critical mismatch #3
- **Problem:** Subscription tiers and lead magnet contact-capture gating operate independently. Dual gating systems.
- **Fix:** Add `get_effective_access_level(user_id, session)` to `tier_control.py` that merges subscription tier + lead magnet state.
- **Files:** `src/subscription/tier_control.py`

---

## Phase 1 — Go-Live Blockers

### Legal/Compliance Blockers

| ID | Finding | Source | Fix Location |
|----|---------|--------|-------------|
| **L-01** | Consent stored in-memory dict (`_acknowledgments = {}`), lost on restart. No durable audit trail, no IP/UA captured. | Legal 7A | `src/web/intelligent_advisor_api.py:406-431` → database table `consent_audit_log` |
| **L-02** | Automatic lead transmission to CPA at lead_score >= 60 without explicit user consent dialog. | Legal 7B | `src/web/static/js/advisor/modules/advisor-data.js:615` → add consent dialog before `sendLeadToCPA()` |
| **L-03** | Privacy Policy omits Anthropic/OpenAI as data processors. User financial data sent to LLMs undisclosed. | Legal 3B | `src/web/templates/privacy.html` → add Section 4.3 |
| **L-04** | Client report emails missing ALL CAN-SPAM elements: no physical address, no unsubscribe, no sender ID, no privacy link. | Legal 4A | `src/web/advisor/report_generation.py:323-335` → email template overhaul |
| **L-05** | AI-generated narratives not labeled as AI-generated. Claude prompt explicitly removes disclaimers. Users cannot distinguish AI from human CPA analysis. | Legal 2A | `src/advisory/ai_narrative_generator.py:484-496` → add AI badge; `src/web/templates/advisory_report_preview.html` |

### Security Blockers

| ID | Finding | Source | Fix Location |
|----|---------|--------|-------------|
| **S-01** | PII (client name, income, savings figures) sent to Anthropic/OpenAI without scrubbing or anonymization. GLBA violation risk. | Security 1 | `src/advisory/ai_narrative_generator.py:430-466`, `src/advisory/report_summarizer.py:340-370` → PII scrubbing layer |

### QA Blockers

| ID | Finding | Source | Fix Location |
|----|---------|--------|-------------|
| **Q-01** | `report_summarizer.py` has zero test coverage. All 4 public methods untested. | QA RS-01 | `tests/unit/test_report_summarizer.py` (new) |
| **Q-02** | `advisory_pdf_exporter.py` has no dedicated test. PDF pipeline entirely untested end-to-end. | QA PDF-01 | `tests/unit/test_advisory_pdf_exporter.py` (new) |
| **Q-03** | `report_generator.py` line 181: `tax_return.taxpayer` can be None → double AttributeError (first in main path, again in error recovery). | QA RG-02 | `src/advisory/report_generator.py:181,252` → null guard |

### Product-Technical Blockers (from Architect Audit)

| ID | Finding | Source | Fix Location |
|----|---------|--------|-------------|
| **P-01** | Same as F0-A (lead magnet schema mismatch) | Architect | See F0-A |
| **P-02** | Same as F0-B (PDF gate dead code) | Architect | See F0-B |
| **P-03** | Same as F0-C (dual gating systems) | Architect | See F0-C |

---

## Phase 2 — High Severity

### QA High

| ID | Finding | Fix Location |
|----|---------|-------------|
| **Q-04** | `_calculate_effective_rate` uses `agi = adjusted_gross_income or 1` — zero AGI gets effective rate calculated against $1 instead of returning 0.0. Same bug in `recommendation_engine.py:198`. | `report_generator.py:607`, `recommendation_engine.py:198` → change to `or 0` |
| **Q-05** | Hardcoded `tax_year=2025` in `ComprehensiveRecommendation` — ignores `tax_return.tax_year`. | `recommendation_engine.py:267` |
| **Q-06** | AI singleton `get_narrative_generator()` not thread-safe (double-checked locking). Same for `get_report_summarizer()`. | `ai_narrative_generator.py:586-593`, `report_summarizer.py` |
| **Q-07** | AI in-memory cache (`self._cache: Dict`) not thread-safe under concurrent report generation. | `ai_narrative_generator.py:113`, `report_summarizer.py` |
| **Q-08** | No full pipeline integration test: Profile → Calculation → Recommendations → PDF. | `tests/integration/` (new test) |
| **Q-09** | 3 of 4 `AINarrativeGenerator` methods have no fallback tests. | `tests/unit/test_ai_report_narratives.py` |
| **Q-10** | No input range validators on ANY income/deduction/age field in `TaxProfileInput`. Negative values, extreme values flow to calculator unchecked. | `src/web/advisor/models.py` |

### Security High

| ID | Finding | Fix Location |
|----|---------|-------------|
| **S-02** | PDF download tier gate not enforced (same as F0-B). | See F0-B |
| **S-03** | `get_or_create_session` auto-creates sessions on miss — no 404 on invalid session_id. No user-to-session ownership binding. | `report_routes.py:134`, `report_generation.py:53` |
| **S-04** | Logo upload allows SVG (XSS risk via embedded scripts). Trusts Content-Type without magic-byte verification. `cpa_id` parameter unvalidated — no authz check. Existing `file_upload_security.py` not used. | `report_generation.py:384-416` |

### DevOps High

| ID | Finding | Fix Location |
|----|---------|-------------|
| **D-01** | Redis singleton not re-initialized after connection loss. Cached broken instance returned forever. | `redis_session_persistence.py:674` |
| **D-02** | No overall timeout on `generate_report()`. Sequential engine calls can block indefinitely. | `report_generator.py` |
| **D-03** | `proxy_read_timeout 120s` missing on page routes (`location /`). Falls back to nginx default 60s. | `nginx/nginx.production.conf` |
| **D-04** | No AI provider health check in `/health/ready`. Expired API keys only surface on first user request. | `src/web/health_checks.py` |

### Legal High

| ID | Finding | Fix Location |
|----|---------|-------------|
| **L-06** | Consent modal says "auto-deleted after 30 days" but Redis TTL is 24 hours. Material misrepresentation. | `src/web/templates/intelligent_advisor.html:50`, `redis_session_persistence.py:133` |
| **L-07** | Terms of Service doesn't mention AI processing or LLM provider data sharing. | `src/web/templates/terms.html` |
| **L-08** | AI fallback narratives carry no disclaimer and are indistinguishable from AI-generated content. | `ai_narrative_generator.py:517-552` |
| **L-09** | Circular 230 statutory language missing from `advisory_report_preview.html` (primary report view). | `src/web/templates/advisory_report_preview.html` |

---

## Phase 3 — Medium Severity

### QA Medium

| ID | Finding | Fix Location |
|----|---------|-------------|
| **Q-11** | `dependents: Optional[int] = 0` allows negative values. | `models.py` |
| **Q-12** | `capital_gains` and `capital_gains_long` can conflict — no `@root_validator`. | `models.py` |
| **Q-13** | Exception swallowing in `_generate_executive_summary` catches all exceptions including `MemoryError`. | `report_generator.py:327-328` |
| **Q-14** | `_generate_recommendations()` not individually guarded — failure kills entire report. | `report_generator.py` |

### Security Medium

| ID | Finding | Fix Location |
|----|---------|-------------|
| **S-05** | No size limits on `conversation_history` (unbounded list), `message` (no max_length), `state` (no pattern validation). DoS + prompt injection risk. | `models.py:110-128` |
| **S-06** | PDF rate limiter silently disabled when module unavailable. Keyed on session_id not user — easy bypass. | `report_routes.py:115-129` |
| **S-07** | Redis session encryption fails open to plaintext on import error. | `redis_session_persistence.py:36-51` |
| **S-08** | CORS falls back to empty allowlist with only a warning. `allow_credentials=True` set unconditionally. | `middleware_setup.py:36-62` |
| **S-09** | Entire `/api/advisor/` CSRF-exempt. Protection relies solely on CORS + custom header. | `middleware_setup.py:170` |

### DevOps Medium

| ID | Finding | Fix Location |
|----|---------|-------------|
| **D-05** | `TaxCalculator.calculate_complete_return()` called twice per report (redundant). | `report_generator.py` |
| **D-06** | No concurrent PDF generation limit. No async offload for `doc.build()`. | `advisory_pdf_exporter.py` |
| **D-07** | PDF temp files not cleaned up on build error. | `advisory_pdf_exporter.py` |
| **D-08** | Perplexity adapter missing `asyncio.wait_for` timeout. | `unified_ai_service.py:449-478` |
| **D-09** | AI config not validated at startup (unlike DB, Redis, Sentry). | `app.py` startup |
| **D-10** | Nginx rate limiting uses `$binary_remote_addr` — broken behind load balancer. | `nginx.production.conf` |
| **D-11** | `_check_budget_alerts()` is a no-op (line 700: `pass`). Budget alerts never dispatched. | `metrics_service.py:700` |
| **D-12** | `_generate_recommendations()` not individually try/except wrapped. | `report_generator.py` |
| **D-13** | No retry mechanism for transient engine failures. | `report_generator.py` |

### Legal Medium

| ID | Finding | Fix Location |
|----|---------|-------------|
| **L-10** | `generate-report` API response uses non-compliant Circular 230 language. | `report_generation.py:285-289` |
| **L-11** | GDPR/CCPA provisions incomplete: no DPA reference, no Art. 22 automated decision-making disclosure. | `privacy.html` |

### Product-Technical Medium (from Architect Audit)

| ID | Finding | Fix Location |
|----|---------|-------------|
| **PM-01** | Chat strategy tiers disconnected from subscription tiers. | `intelligent_advisor_api.py`, `tier_control.py` |
| **PM-02** | PDF exporter has no tier-aware section filtering. | `advisory_pdf_exporter.py` |
| **PM-03** | Preview template shows download button to ALL users. | `advisory_report_preview.html` |

---

## Phase 4 — Enhancement Spec (9 Items)

Full spec at: `docs/superpowers/specs/2026-03-18-advisory-report-enhancements-design.md`

| # | Enhancement | Priority | Key File |
|---|-------------|----------|----------|
| 1 | Pro Forma Comparison (actual savings delta) | P0 | `report_generator.py` |
| 2 | State Tax Fix (run state engine on optimized clone) | P0 | `report_generator.py` |
| 3 | AI Call Parallelization (under 15s target) | P1 | `report_generation.py` |
| 4 | Scenario Analysis Integration (wire existing ScenarioService) | P1 | `report_generator.py` |
| 5 | Confidence-Driven CTAs (tell users what data to provide) | P1 | `report_generator.py` |
| 6 | AI Reasoning Layer (Claude validates strategies) | P2 | `report_generator.py` |
| 7 | Dual Projections (with/without strategy comparison) | P2 | `report_generator.py` |
| 8 | Salary Curve (S-corp salary optimization) | P2 | `report_generator.py` |
| 9 | Strategy Interaction Modeling (cumulative deepcopy) | P3 | `report_generator.py` |

---

## Phase 5 — Product PRDs (6 Items)

| # | PRD | Priority | Key Files |
|---|-----|----------|-----------|
| PRD-1 | Tier Gating for New Report Sections | P1 | `tier_control.py`, `report_generator.py`, `advisory_pdf_exporter.py` |
| PRD-2 | Lead Score Update from Report Engagement | P1 | `intelligent_advisor_api.py`, `report_generation.py` |
| PRD-3 | CPA vs Client View Distinction | P2 | `report_generator.py`, `advisory_report_preview.html` |
| PRD-4 | Data CTAs for Chatbot Re-engagement | P2 | `report_generator.py`, `intelligent_advisor.html` |
| PRD-5 | A/B Testing Hook | P3 | `report_generator.py` |
| PRD-6 | AI Reasoning with Conversation History | P3 | `ai_narrative_generator.py`, `intelligent_advisor_api.py` |

---

## Implementation Order

### Week 1 — Legal Blockers + Foundation Fixes (MUST before any traffic)

1. **L-01** — Consent persistence to database
2. **L-02** — Lead transmission consent dialog
3. **L-03** — Privacy Policy LLM disclosure
4. **L-04** — CAN-SPAM email compliance
5. **L-05** — AI-generated content labeling
6. **S-01** — PII scrubbing for AI prompts
7. **F0-B** — PDF tier enforcement
8. **F0-C** — Unified gating model

### Week 2 — Security + QA Blockers

9. **Q-03** — Null taxpayer guard
10. **S-03** — Replace `get_or_create_session` with `get_session_only` in report handlers
11. **S-04** — Logo upload: remove SVG, use `file_upload_security.py`, authz check
12. **Q-01** — Tests for `report_summarizer.py`
13. **Q-02** — Tests for `advisory_pdf_exporter.py`
14. **F0-A** — Schema bridge for lead magnet templates
15. **Q-10** — Input validators on `TaxProfileInput`
16. **S-05** — Size limits on `conversation_history`/`message`

### Week 3 — High Severity Fixes

17. **Q-04** — Fix `agi or 1` → `agi or 0` (2 locations)
18. **Q-05** — Fix hardcoded `tax_year=2025`
19. **Q-06/Q-07** — Thread-safe AI singletons + cache
20. **D-01** — Redis singleton reconnection
21. **D-02** — Overall timeout on `generate_report()`
22. **D-03** — Nginx `proxy_read_timeout` on page routes
23. **D-04** — AI provider health check
24. **L-06** — Fix TTL vs consent modal mismatch
25. **L-07/L-09** — ToS AI disclosure + Circular 230 on preview page

### Week 4 — Medium Severity + Performance

26-39. All medium severity items (S-06 through D-13, L-10/L-11, PM-01 through PM-03)

### Week 5+ — Enhancements & PRDs

40-48. Enhancement spec items 1-9
49-54. PRD items 1-6

---

## Cross-Reference: Deduplicated Overlaps

| Finding appears in multiple audits | Canonical ID |
|---|---|
| PDF tier gate not enforced | F0-B = S-02 = P-02 |
| PII to AI providers | S-01 ≈ L-03 (different angles: security vs privacy disclosure) |
| No input validation on TaxProfileInput | Q-10 ≈ S-05 (overlapping but different fields) |
| Consent not persisted | L-01 (unique to legal) |
| AI content not labeled | L-05 ≈ L-08 (different surfaces) |
| `_generate_recommendations()` not guarded | Q-14 = D-12 |
| Lead magnet schema mismatch | F0-A = P-01 |
| Dual gating systems | F0-C = P-03 |
