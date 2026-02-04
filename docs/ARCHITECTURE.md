# GBO CPA TAI Platform - Architecture Diagram

## System Overview

```
+=====================================================================================+
|                           GBO CPA TAX AI PLATFORM                                   |
|                        FastAPI (Python) - Tax Year 2025                             |
+=====================================================================================+

                        +---------------------------+
                        |      CLIENT LAYER         |
                        +---------------------------+
                        | Browser (Jinja2 Templates)|
                        | React/Vite SPA (port 3000)|
                        | WebSocket Clients         |
                        | External Webhooks         |
                        | Stripe Payments           |
                        +-------------+-------------+
                                      |
                                      | HTTPS / WSS
                                      v
+======================================================================================+
|                        EDGE / SECURITY MIDDLEWARE                                     |
|--------------------------------------------------------------------------------------|
|  SecurityHeadersMiddleware --> CSRFMiddleware --> RateLimitMiddleware                 |
|  --> RequestValidationMiddleware --> CORSMiddleware --> InputValidationMiddleware     |
|  --> TenantIsolationMiddleware                                                       |
|                                                                                      |
|  [src/security/middleware.py, src/security/input_validation_middleware.py,            |
|   src/security/tenant_isolation_middleware.py]                                        |
+======================================================================================+
                                      |
          +---------------------------+----------------------------+
          |                           |                            |
          v                           v                            v
+---------+--------+    +-------------+-----------+    +-----------+----------+
|  WEB LAYER       |    |  CORE API               |    |  PANEL APIs          |
|  (End Users)     |    |  (Multi-Tenant SaaS)    |    |  (CPA & Admin)       |
+------------------+    +-------------------------+    +----------------------+


========================================================================================
                              WEB LAYER (src/web/)
========================================================================================

+------------------+  +-------------------+  +---------------------+  +----------------+
| Chat & AI        |  | Filing & Forms    |  | Tax Analysis        |  | Admin & Config |
|------------------|  |-------------------|  |---------------------|  |----------------|
| ai_chat_api      |  | unified_filing    |  | advisory_api        |  | config_api     |
| express_lane_api |  | guided_filing_api |  | scenario_api        |  | audit_api      |
| intelligent_     |  | draft_forms_api   |  | capital_gains_api   |  | sessions_api   |
|  advisor_api     |  | filing_package    |  | k1_basis_api        |  | workspace_api  |
| unified_advisor  |  | smart_tax_api     |  | rental_deprec_api   |  | auto_save_api  |
| recommendation_  |  |                   |  |                     |  | mfa_api        |
|  helper          |  |                   |  |                     |  | feature_access |
+------------------+  +-------------------+  +---------------------+  +----------------+

+---------------------------------------------+  +-------------------------------------+
| Routers (src/web/routers/)                   |  | Tenant & Branding                   |
|---------------------------------------------|  |-------------------------------------|
| /api/calculations  - tax calculations        |  | cpa_branding_api  - white-label      |
| /api/documents     - document upload/manage  |  | custom_domain_api - custom domains   |
| /api/returns       - tax return CRUD         |  | admin_tenant_api  - tenant mgmt      |
| /api/scenarios     - what-if scenarios       |  | admin_user_mgmt   - user management  |
| /api/health        - health/readiness        |  +-------------------------------------+
| /api/validation    - input validation        |
| /pages/*           - server-rendered pages   |
+---------------------------------------------+


========================================================================================
                          CORE API (src/core/api/)
========================================================================================

+-------------------+  +---------------------+  +---------------------+
| Authentication    |  | Tax Returns         |  | Documents           |
|-------------------|  |---------------------|  |---------------------|
| auth_routes       |  | tax_returns_routes  |  | documents_routes    |
| oauth_routes      |  | scenarios_routes    |  |                     |
| users_routes      |  | recommendations_    |  |                     |
|                   |  |   routes            |  |                     |
+-------------------+  +---------------------+  +---------------------+

+-------------------+  +---------------------+
| Billing           |  | Communication       |
|-------------------|  |---------------------|
| billing_routes    |  | messaging_routes    |
| premium_reports   |  |                     |
+-------------------+  +---------------------+


========================================================================================
                    ADMIN PANEL (src/admin_panel/api/)
========================================================================================

+-------------------+  +-------------------+  +--------------------+  +----------------+
| Platform Mgmt     |  | Team & Users      |  | Billing & Subs     |  | Security       |
|-------------------|  |-------------------|  |--------------------|  |----------------|
| superadmin_routes |  | team_routes       |  | billing_routes     |  | auth_routes    |
| dashboard_routes  |  | workflow_routes   |  | platform_billing   |  | rbac_routes    |
| settings_routes   |  | client_routes     |  |                    |  | compliance_    |
| alert_routes      |  | ticket_routes     |  |                    |  |   routes       |
+-------------------+  +-------------------+  +--------------------+  +----------------+


========================================================================================
                    CPA PANEL (src/cpa_panel/api/)  -- White-Label $20K/yr
========================================================================================

+-------------------+  +-------------------+  +--------------------+  +----------------+
| Client Mgmt       |  | Lead Gen & Sales  |  | Analysis & Reports |  | Operations     |
|-------------------|  |-------------------|  |--------------------|  |----------------|
| client_portal_    |  | lead_routes       |  | analysis_routes    |  | workflow_      |
|   routes          |  | lead_generation_  |  | insights_routes    |  |   routes       |
| client_visibility |  |   routes          |  | aggregated_        |  | task_routes    |
| document_routes   |  | lead_magnet_      |  |   insights_routes  |  | staff_routes   |
| intake_routes     |  |   routes          |  | report_routes      |  | deadline_      |
| smart_onboarding  |  | funnel_routes     |  | scenario_routes    |  |   routes       |
| notes_routes      |  | pipeline_routes   |  | optimizer_routes   |  | appointment_   |
| data_routes       |  | pricing_routes    |  | exposure_routes    |  |   routes       |
|                   |  |                   |  | practice_intel     |  | invoice_routes |
+-------------------+  +-------------------+  +--------------------+  +----------------+

+-------------------+  +-------------------+
| Engagement        |  | Payments          |
|-------------------|  |-------------------|
| engagement_routes |  | payment_settings  |
| notification_     |  | (Stripe Connect)  |
|   routes          |  |                   |
+-------------------+  +-------------------+


          +---------------------------+----------------------------+
          |                           |                            |
          v                           v                            v
========================================================================================
                         SERVICE / BUSINESS LOGIC LAYER
========================================================================================

+-------------------------------+  +----------------------------------+
|  TAX CALCULATION ENGINE       |  |  AI / ML SERVICES                |
|  (src/calculator/)            |  |  (src/services/ai/, src/agent/)  |
|-------------------------------|  |----------------------------------|
|  engine.py         - core tax |  |  unified_ai_service  - AI router |
|  tax_calculator.py - facade   |  |  tax_reasoning       - GPT tax   |
|  audited_engine.py - w/audit  |  |  tax_research        - research  |
|  qbi_calculator.py - QBI/199A|  |  compliance_reviewer  - AI review |
|  sstb_classifier   - SSTB    |  |  anomaly_detector     - fraud    |
|  decimal_math.py   - money   |  |  chat_router          - AI chat  |
|  tax_year_config   - brackets|  |  rate_limiter          - AI rate  |
|  validation.py     - inputs  |  |  tax_agent.py         - OpenAI   |
|  recommendations   - basic   |  |  intelligent_tax_agent - full AI |
+-------------------------------+  +----------------------------------+

+-------------------------------+  +----------------------------------+
|  TAX SERVICES                 |  |  OCR / DOCUMENT PROCESSING       |
|  (src/services/)              |  |  (src/services/ocr/)             |
|-------------------------------|  |----------------------------------|
|  calculation_pipeline  - orch |  |  ocr_engine          - Tesseract|
|  cached_calc_pipeline  - $$$  |  |  document_processor   - pipeline|
|  async_calc_pipeline   - bg   |  |  field_extractor      - fields  |
|  tax_return_service    - CRUD |  |  confidence_scorer    - scoring  |
|  scenario_service      - sims |  |  ai_enhanced_processor- GPT OCR |
|  tax_opportunity_detector     |  |  inference_engine     - ML infer|
|  tax_law_interpreter   - law  |  |  resilient_processor  - retry   |
|  unified_tax_advisor   - all  |  +----------------------------------+
|  validation_service    - val  |
|  rental_depreciation   - MACRS|  +----------------------------------+
|  case_matcher          - sim  |  |  RECOMMENDATION ENGINE            |
|  workspace_service     - ws   |  |  (src/recommendation/)            |
|  client_communicator   - msg  |  |----------------------------------|
|  cpa_intelligence      - biz  |  |  recommendation_engine - rules   |
|  ai_knowledge_base     - KB   |  |  rules_based_recommender - logic |
|  multimodal_support    - imgs |  |  ai_enhancer           - AI recs |
+-------------------------------+  |  filing_status_optimizer         |
                                    +----------------------------------+

+-------------------------------+  +----------------------------------+
|  ADVISORY REPORTS             |  |  CPA PANEL SERVICES              |
|  (src/advisory/)              |  |  (src/cpa_panel/services/)       |
|-------------------------------|  |----------------------------------|
|  report_generator    - build  |  |  advisory_report_service         |
|  report_summarizer   - summ   |  |  smart_onboarding_service        |
|  ai_narrative_gen    - GPT    |  |  lead_generation_service         |
+-------------------------------+  |  lead_magnet_service             |
                                    |  funnel_orchestrator             |
+-------------------------------+  |  pipeline_service                |
|  EXPORT / PDF                 |  |  intake_service                  |
|  (src/export/)                |  |  scenario_service                |
|-------------------------------|  |  activity_service                |
|  advisory_pdf_exporter        |  |  notification_service            |
|  computation_statement        |  |  nurture_service                 |
|  premium_report_generator     |  |  ai_lead_intelligence            |
|  pdf_visualizations           |  |  ai_question_generator           |
|  professional_formats         |  |  client_researcher               |
|  data_importer (XML)          |  |  report_templates                |
+-------------------------------+  +----------------------------------+

+-------------------------------+  +----------------------------------+
|  RULES ENGINE                 |  |  SMART TAX                       |
|  (src/rules/)                 |  |  (src/smart_tax/)                |
|-------------------------------|  |----------------------------------|
|  rule_engine.py    - YAML     |  |  orchestrator.py     - pipeline  |
|  foreign_assets_rules         |  |  document_processor  - intake    |
+-------------------------------+  +----------------------------------+

+-------------------------------+  +----------------------------------+
|  PROJECTION                   |  |  ONBOARDING                      |
|  (src/projection/)            |  |  (src/onboarding/)               |
|-------------------------------|  |----------------------------------|
|  multi_year projections       |  |  interview_flow      - Q&A flow |
|  what-if analysis             |  |  document_collector   - docs     |
+-------------------------------+  +----------------------------------+


========================================================================================
                    DATA MODELS (src/models/) - 49 IRS Form Models
========================================================================================

+-------------------+  +-------------------+  +--------------------+  +----------------+
| Core Models       |  | Schedules         |  | IRS Forms          |  | Specialized    |
|-------------------|  |-------------------|  |--------------------|  |----------------|
| tax_return.py     |  | schedule_a (A)    |  | form_1040_es       |  | k1_basis       |
| taxpayer.py       |  | schedule_b (B)    |  | form_1040x (amend) |  | income_legacy  |
| income.py         |  | schedule_c (C)    |  | form_1099_*        |  | _decimal_utils |
| deductions.py     |  | schedule_d (D)    |  | form_2210 (penalty)|  |                |
| credits.py        |  | schedule_e (E)    |  | form_2555 (foreign)|  |                |
|                   |  | schedule_f (F)    |  | form_3115 (acctg)  |  |                |
|                   |  | schedule_h (H)    |  | form_4562 (deprec) |  |                |
|                   |  | schedule_1,2,3    |  | form_8949 (gains)  |  |                |
|                   |  |                   |  | form_8995 (QBI)    |  |                |
|                   |  |                   |  | + 20 more forms    |  |                |
+-------------------+  +-------------------+  +--------------------+  +----------------+


========================================================================================
                         INFRASTRUCTURE / CROSS-CUTTING
========================================================================================

+-------------------------------+  +----------------------------------+
|  DATABASE & PERSISTENCE       |  |  SECURITY                        |
|  (src/database/)              |  |  (src/security/)                 |
|-------------------------------|  |----------------------------------|
|  PostgreSQL (async, Alembic)  |  |  authentication.py  - JWT auth   |
|  SQLite (tenant, session)     |  |  middleware.py       - CSRF/CSP  |
|  async_engine     - SA async  |  |  auth_decorators.py  - @require  |
|  persistence.py   - core      |  |  tenant_isolation.py - multi-ten |
|  tenant_persistence - tenant  |  |  file_upload_security- magic     |
|  session_persistence- state   |  |  encryption.py       - AES      |
|  encrypted_fields - PII AES   |  |  encrypted_fields    - PII      |
|  repositories/    - DDD repos |  |  ssn_hash.py         - HMAC SSN |
|    tax_return_repository      |  |  data_sanitizer      - PII mask |
|    user_auth_repository       |  |  secure_serializer   - signing  |
|    client_repository          |  |  fraud_detector      - anomaly  |
|    advisory_repository        |  |  ai_compliance_reviewer         |
|    scenario_repository        |  |  safe_xml.py         - XXE safe |
|    event_store                |  |  secure_logger       - PII log  |
|  unit_of_work     - UoW      |  |  validation.py       - input    |
|  transaction.py   - txns     |  +----------------------------------+
|  pool_monitor     - health    |
|  etl.py           - migration |  +----------------------------------+
|  schema.py        - DDL       |  |  RBAC (src/rbac/)                |
+-------------------------------+  |----------------------------------|
                                    |  jwt.py    - token create/verify |
+-------------------------------+  |  roles     - permission matrix   |
|  CACHE (src/cache/)           |  +----------------------------------+
|-------------------------------|
|  redis_client.py  - Redis     |  +----------------------------------+
|  key-prefix: "tax:"           |  |  REALTIME (src/realtime/)        |
+-------------------------------+  |----------------------------------|
                                    |  websocket_routes  - WS endpts  |
+-------------------------------+  |  connection_manager- WS pool     |
|  RESILIENCE (src/resilience/) |  |  events.py         - event types|
|-------------------------------|  +----------------------------------+
|  circuit_breaker.py           |
|  retry.py (w/jitter)          |  +----------------------------------+
+-------------------------------+  |  WEBHOOKS (src/webhooks/)        |
                                    |----------------------------------|
+-------------------------------+  |  service.py   - delivery/retry   |
|  TASKS (src/tasks/)           |  |  router.py    - CRUD endpoints   |
|-------------------------------|  |  triggers.py  - event dispatch    |
|  celery_app.py  - Celery      |  |  models.py    - endpoint/delivery|
|  ocr_tasks.py   - async OCR   |  |  events.py    - event definitions|
|  dead_letter.py - failed jobs |  +----------------------------------+
+-------------------------------+
                                    +----------------------------------+
+-------------------------------+  |  NOTIFICATIONS (src/notifications)|
|  AUDIT (src/audit/)           |  |----------------------------------|
|-------------------------------|  |  smtp_provider.py    - SMTP      |
|  audit_trail.py   - trail     |  |  ses_provider.py     - AWS SES  |
|  audit_logger.py  - logging   |  |  sendgrid_provider   - SendGrid |
|  immutable_snapshot- freeze   |  |  email_provider.py   - abstract |
|  unified/                     |  |  email_triggers.py   - events   |
|    entry.py   - HMAC entries  |  |  notification_integration       |
|    storage.py - SQLite store  |  +----------------------------------+
|    service.py - query/report  |
|    event_types.py             |  +----------------------------------+
+-------------------------------+  |  SUBSCRIPTION (src/subscription/)|
                                    |----------------------------------|
+-------------------------------+  |  tier_control.py - feature gates |
|  DOMAIN (src/domain/)         |  +----------------------------------+
|-------------------------------|
|  event_bus.py - pub/sub       |  +----------------------------------+
|  domain events for DDD        |  |  CONFIG (src/config/)            |
+-------------------------------+  |----------------------------------|
                                    |  settings.py     - Pydantic cfg |
                                    |  tax_config_loader - YAML rates |
                                    |  ai_providers.py  - AI config   |
                                    +----------------------------------+


========================================================================================
                              DATA FLOW DIAGRAM
========================================================================================

  [Client Browser / SPA]
          |
          | 1. HTTPS Request
          v
  +-------+--------+
  | Security Stack  |  CSP Headers -> CSRF -> Rate Limit -> Input Validation
  +-------+--------+  -> Tenant Isolation -> RBAC
          |
          | 2. Authenticated + Validated Request
          v
  +-------+---------+     +-----------------+     +------------------+
  | API Router      |---->| Auth Service    |---->| JWT Verification |
  | (FastAPI)       |     | (src/core/)     |     | (src/security/)  |
  +-------+---------+     +-----------------+     +------------------+
          |
          | 3. Route to appropriate handler
          v
  +-------+---+-----+---------+---------+-----------+
  |           |     |         |         |           |
  v           v     v         v         v           v
+-----+  +------+ +----+ +-------+ +--------+ +--------+
|Chat |  |Filing| |OCR | |Scenar.| |Advisory| |CPA Ops |
|API  |  |API   | |API | |API    | |Reports | |Panel   |
+--+--+  +--+---+ +-+--+ +---+---+ +---+----+ +---+----+
   |        |       |        |         |           |
   v        v       v        v         v           v
+--+--------+-------+--------+---------+-----------+-----+
|              SERVICE LAYER                              |
|  Calculation Pipeline -> Tax Calculator Engine          |
|  Recommendation Engine -> AI Enhancer -> GPT-4          |
|  OCR Engine -> Field Extractor -> AI Enhanced Processor |
|  Scenario Service -> What-If Analysis                   |
|  Advisory Generator -> AI Narrative -> PDF Export        |
|  Smart Tax Orchestrator -> Document Processor           |
+--+--------------------------------------------------+--+
   |                                                   |
   v                                                   v
+--+--------------+                    +---------------+--+
|  AUDIT TRAIL    |                    |  DOMAIN EVENTS   |
|  (Every write   |                    |  (Event Bus)     |
|   is logged     |                    |  -> Webhooks     |
|   w/HMAC sig)   |                    |  -> Notifications|
+---------+-------+                    |  -> Real-time WS |
          |                            +--------+---------+
          v                                     |
+---------+-------+                    +--------+---------+
| PERSISTENCE     |                    | EXTERNAL         |
|-----------------|                    |------------------|
| PostgreSQL      |                    | OpenAI GPT-4     |
|  (async, pool)  |                    | Stripe Connect   |
| SQLite          |                    | AWS SES          |
|  (tenant/audit) |                    | SendGrid         |
| Redis           |                    | SMTP             |
|  (cache/session)|                    | Tesseract OCR    |
+-----------------+                    +------------------+


========================================================================================
                         MULTI-TENANT ARCHITECTURE
========================================================================================

                    +---------------------------+
                    |    PLATFORM ADMIN          |
                    |    (Superadmin Panel)      |
                    |    /admin/api/*            |
                    +-------------+-------------+
                                  |
                    +-------------+-------------+
                    |    FIRM (TENANT)           |
                    |    Isolated by firm_id     |
                    +----+--------+--------+----+
                         |        |        |
                   +-----+--+ +--+-----+ ++------+
                   | CPA    | | CPA    | | CPA   |
                   | User   | | User   | | User  |
                   | (Admin)| |(Preparer|(Review)|
                   +----+---+ +--+-----+ +--+----+
                        |        |           |
                   +----+--------+-----------+----+
                   |       CLIENT PORTAL          |
                   |  (White-labeled per firm)     |
                   |  Custom domain + branding     |
                   +------------------------------+
                        |        |           |
                   +----+--+ +--+-----+ +---+----+
                   |Client | |Client  | |Client  |
                   |Portal | |Onboard | |Docs    |
                   +-------+ +--------+ +--------+


========================================================================================
                        TAX CALCULATION PIPELINE
========================================================================================

  [Tax Return Data]
        |
        v
  +-----+------+
  | Validation  |  Input validation, SSN format, filing status
  +-----+------+
        |
        v
  +-----+------+
  | Calculator  |  49 IRS form models -> engine.py
  | Engine      |  Brackets, deductions, credits, AMT
  +-----+------+
        |
        +--------+--------+---------+
        |        |        |         |
        v        v        v         v
  +-----+-+ +---+---+ +--+--+ +----+----+
  |QBI/   | |Capital| |AMT  | |Estimated|
  |199A   | |Gains  | |Form | |Tax 1040 |
  |Calc   | |8949/D | |6251 | |ES       |
  +---+---+ +---+---+ +--+--+ +----+----+
      |        |        |         |
      v        v        v         v
  +---+--------+--------+---------+---+
  | AUDITED ENGINE (w/audit trail)    |
  | Every calculation step logged     |
  +---+-------------------------------+
      |
      v
  +---+-------------------+
  | Recommendation Engine |
  | Rules-based + AI      |
  | Filing Status Optimizer|
  +---+-------------------+
      |
      v
  +---+-------------------+
  | Advisory Report       |
  | AI Narrative Gen      |
  | PDF / HTML Export     |
  +---+-------------------+


========================================================================================
                      TECHNOLOGY STACK SUMMARY
========================================================================================

  BACKEND:    Python 3.11+, FastAPI, Uvicorn
  DATABASE:   PostgreSQL (primary), SQLite (tenant/audit), Redis (cache)
  AUTH:       JWT (HS256), bcrypt, RBAC, MFA (TOTP via pyotp)
  AI/ML:     OpenAI GPT-4, TF-IDF classifiers, ensemble ML
  OCR:       Tesseract, AI-enhanced extraction
  PAYMENTS:  Stripe Connect (white-label billing)
  EMAIL:     SMTP, AWS SES, SendGrid
  REALTIME:  WebSocket (FastAPI native)
  TASKS:     Celery (async OCR, background jobs)
  EXPORT:    ReportLab (PDF), Jinja2 (HTML)
  SECURITY:  CSRF, CSP, CORS, rate limiting, PII encryption (AES),
             HMAC audit trails, tenant isolation, file upload validation
  FRONTEND:  Jinja2 SSR + vanilla JS, Vite/React SPA option
```

## Key Data Flows

### 1. Tax Return Filing Flow
```
Client uploads W-2 (PDF) -> OCR extracts fields -> AI validates ->
Populates TaxReturn model -> Calculator engine runs -> Recommendations generated ->
Advisory report created -> CPA reviews -> PDF exported -> E-file ready
```

### 2. CPA Client Acquisition Flow
```
Lead magnet page -> Prospect fills form -> AI lead scoring ->
Pipeline stage tracking -> Nurture emails -> Smart onboarding ->
Document collection -> Engagement letter (e-sign) -> Client portal activated
```

### 3. Multi-Tenant Isolation
```
Every request -> Tenant ID extracted from JWT/session ->
All DB queries filtered by firm_id -> Audit trail tagged with tenant ->
WebSocket rooms scoped to firm -> Cache keys prefixed per tenant
```
