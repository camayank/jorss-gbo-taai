# Client Journey Orchestrator — Design Document

**Date:** 2026-03-04
**Status:** Approved
**Priority:** Highest — smooth, interconnected UX across all subsystems

---

## Problem Statement

The platform has excellent individual subsystems (Advisor, Documents, Returns, Scenarios, CPA Review, Billing) that work independently but operate as **islands**. Users hit dead-ends where completing one step doesn't lead to the next. There's no orchestration layer connecting subsystems into a coherent client tax journey.

**User-reported experience:** "I finished the advisor but now what? Where do I upload documents? How does my return get created?"

## Requirements

1. **No dead-ends** — every user action leads somewhere meaningful
2. **Event-driven** — subsystems stay independent, communicate via events
3. **Journey visibility** — user sees progress through the tax journey at all times
4. **Context-aware CTAs** — every page suggests the logical next step
5. **Fixes 9 AI audit issues** — prompt injection, PII, cost caps, fallbacks, model config, CPA escalation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EVENT BUS (In-Process)                     │
│  advisor.profile_complete │ document.processed │ return.ready │
│  scenario.created │ review.submitted │ report.generated       │
└────────┬──────────────┬──────────────┬──────────────┬────────┘
         │              │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
    │Advisor  │   │ Document  │  │ Return  │  │ Scenario  │
    │Service  │   │ Service   │  │ Service │  │ Service   │
    └─────────┘   └───────────┘  └─────────┘  └───────────┘
         │              │              │              │
    ┌────▼────────────────────────────────────────────▼────────┐
    │           CLIENT JOURNEY ORCHESTRATOR                     │
    │  Tracks: INTAKE → PROFILING → DOCS → RETURN →            │
    │          SCENARIOS → CPA_REVIEW → REPORT → FILED         │
    │  Emits: next_step suggestions for frontend               │
    └──────────────────────┬───────────────────────────────────┘
                           │
    ┌──────────────────────▼───────────────────────────────────┐
    │           FRONTEND: Journey Progress + CTAs               │
    │  [✓ Profile] [✓ Documents] [◉ Return] [ Scenarios] ...  │
    └──────────────────────────────────────────────────────────┘
```

**Key principle:** Subsystems emit events, don't call each other. Only the orchestrator knows the full journey.

---

## Component 1: Event Bus

**File:** `src/events/event_bus.py`

Lightweight in-process event bus. No external dependencies (no Redis/Kafka). Thread-safe using `threading.Lock` (same pattern as `TenantScopedStore`).

### Event Types (8 total)

| Event | Emitted By | Data |
|-------|-----------|------|
| `AdvisorProfileComplete` | intelligent_advisor_api.py | session_id, profile_completeness, extracted_forms |
| `AdvisorMessageSent` | intelligent_advisor_api.py | message text (for input guard) |
| `DocumentProcessed` | documents.py router | document_id, document_type, fields_extracted |
| `ReturnDraftCreated` | returns.py router | return_id, completeness |
| `ReturnReady` | returns.py router | return_id, needs_review |
| `ScenarioCreated` | scenarios.py router | scenario_id, savings_amount |
| `ReviewSubmitted` | CPA review endpoint | return_id, cpa_id |
| `ReportGenerated` | advisory_api.py | report_id, download_url |

### API

```python
event_bus = EventBus()
event_bus.on(AdvisorProfileComplete, handler_fn)  # Subscribe
event_bus.emit(AdvisorProfileComplete(...))        # Publish
```

- Handlers run synchronously in-process
- Errors in handlers are logged but don't block the emitting service
- Thread-safe with `threading.Lock`

---

## Component 2: Client Journey Orchestrator

**File:** `src/services/journey_orchestrator.py`

### Journey Stages

```python
class JourneyStage(str, Enum):
    INTAKE = "intake"
    PROFILING = "profiling"
    DOCUMENTS = "documents"
    RETURN_DRAFT = "return_draft"
    SCENARIOS = "scenarios"
    CPA_REVIEW = "cpa_review"
    REPORT = "report"
    FILED = "filed"
```

### Event Handlers (8 handlers)

Each handler does 3 things:
1. **Takes automatic action** (create draft, apply data, queue for review)
2. **Advances the journey stage**
3. **Sets next-step CTA** for frontend

| Handler | Trigger | Auto-Action | Next Step CTA |
|---------|---------|-------------|---------------|
| `handle_profile_complete` | Profile ≥60% | Create draft return | "Upload your W-2" |
| `handle_message_sent` | Every chat msg | Apply InputGuard | (none) |
| `handle_document_processed` | Doc OCR done | Apply fields to return | "Review Return" or "Upload Another" |
| `handle_return_draft_created` | Draft exists | Check completeness | "Run Scenarios" |
| `handle_return_ready` | Return complete | Suggest CPA review | "Submit for CPA Review" |
| `handle_scenario_created` | Scenario saved | Link to return | "Apply to Return" |
| `handle_review_submitted` | CPA queued | Create lead + assign | "Your CPA will review" |
| `handle_report_generated` | Report ready | Notify client | "Download Report" |

### Journey State Storage

Uses `TenantScopedStore` (already built in `src/security/tenant_scoped_store.py`) for in-memory journey state. Key: `journey:{user_id}`, scoped by tenant_id.

---

## Component 3: Security Integrations (Fixes Audit Issues 1-9)

### 3a. Input Guard (Fix #1: Prompt Injection)

**File:** `src/security/input_guard.py`

```python
INJECTION_PATTERNS = [
    r"(?i)ignore.*previous.*instruction",
    r"(?i)what.*system.*prompt",
    r"(?i)you.*now.*different",
    r"(?i)forget.*all.*instruction",
    r"(?i)override.*rule",
    r"(?i)repeat.*system.*message",
]

def check_input(text: str) -> InputGuardResult:
    # Returns (is_safe, sanitized_text, violation_type)
```

Wired into orchestrator's `handle_message_sent` handler — runs BEFORE message reaches AI.

### 3b. PII Sanitization on Chat Input (Fix #2)

Apply existing `data_sanitizer.sanitize_string()` in the `handle_message_sent` handler before AI call.

### 3c. Per-Session Cost Cap (Fix #3)

Orchestrator tracks cumulative AI cost per journey. Blocks at `MAX_COST_PER_SESSION = $10.00`.

### 3d. Cross-Provider Fallback (Fix #4)

Wrap AI calls in orchestrator with provider chain:
```python
async def ai_with_fallback(capability, prompt):
    for provider in get_provider_priority(capability):
        try:
            return await ai_service.complete(provider=provider, prompt=prompt)
        except (RuntimeError, RateLimitExceededError):
            continue
    return deterministic_fallback(capability, prompt)
```

### 3e. Research/Embeddings Fallback (Fix #5)

Deterministic fallbacks: cached IRS rules for research, TF-IDF for embeddings.

### 3f. Configurable Model Versions (Fix #6)

**File:** `src/config/models.py`

Model versions read from env vars with current hardcoded values as defaults:
```python
OPENAI_FAST_MODEL = os.environ.get("OPENAI_FAST_MODEL", "gpt-4o-mini")
ANTHROPIC_COMPLEX_MODEL = os.environ.get("ANTHROPIC_COMPLEX_MODEL", "claude-opus-4-20250514")
```

### 3g. Per-User Cost Budget (Fix #7)

Journey progress tracks cost per stage per tenant. Configurable per billing plan.

### 3h. Versioned System Prompts (Fix #8)

**Directory:** `src/prompts/`

| File | Content |
|------|---------|
| `tax_agent_v1.txt` | Main intelligent tax agent prompt |
| `reasoning_v1.txt` | Tax reasoning prompt |
| `research_v1.txt` | Research prompt |
| `extraction_v1.txt` | Data extraction prompt |

Loaded by version string. Change version without code deployment.

### 3i. CPA Auto-Escalation (Fix #9)

When confidence < 0.6 on any extraction, orchestrator auto-flags for CPA review and shows: "I'm not confident about this — routing to your CPA for review."

---

## Component 4: Frontend

### 4a. Journey Progress Bar

**File:** `src/web/templates/partials/journey_progress.html`

Added to sidebar, visible on all pages. Shows 8 stages with completion states (done, active, pending).

### 4b. Next Step Banner

**File:** `src/web/templates/partials/next_step_banner.html`

Dismissible banner at top of content area. Context-aware CTA from orchestrator.

### 4c. Alpine Store

**File:** `src/web/static/js/stores/journey.js`

```javascript
Alpine.store('journey', {
    stage: 'intake',
    progress: {},
    nextStep: null,
    async refresh() {
        const res = await fetch('/api/journey/progress');
        // Update stage + progress + nextStep
    }
});
```

### 4d. Inline Connection Points

At key moments within existing pages:

- **Advisor** (after analysis): `[Upload Documents] [See Scenarios] [View Draft Return]`
- **Documents** (after upload): `✓ W-2 processed — 12 fields applied [Review Return]`
- **Scenarios** (after comparison): `Standard deduction saves $2,400 [Apply to Return] [Ask CPA]`
- **Return** (when ready): `Return complete [Submit for CPA Review] [Generate Report]`

---

## Component 5: API Endpoints

**File:** `src/web/routers/journey_api.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/journey/progress` | GET | Current stage + completion % per stage |
| `/api/journey/next-step` | GET | Context-aware next action |
| `/api/journey/stage` | PUT | Manual stage override (admin/CPA) |
| `/api/journey/history` | GET | Timeline of journey events |

---

## New Files

| File | Purpose | Est. Lines |
|------|---------|------------|
| `src/events/event_bus.py` | Event bus + typed events | ~200 |
| `src/events/events.py` | Event dataclass definitions | ~120 |
| `src/services/journey_orchestrator.py` | Journey logic + handlers | ~400 |
| `src/web/routers/journey_api.py` | Journey API endpoints | ~150 |
| `src/security/input_guard.py` | Prompt injection protection | ~100 |
| `src/config/models.py` | Env-configurable model versions | ~80 |
| `src/prompts/tax_agent_v1.txt` | Versioned system prompt | ~50 |
| `src/prompts/reasoning_v1.txt` | Versioned reasoning prompt | ~20 |
| `src/prompts/research_v1.txt` | Versioned research prompt | ~15 |
| `src/prompts/extraction_v1.txt` | Versioned extraction prompt | ~10 |
| `src/web/templates/partials/journey_progress.html` | Progress bar | ~60 |
| `src/web/templates/partials/next_step_banner.html` | CTA banner | ~40 |
| `src/web/static/js/stores/journey.js` | Alpine journey store | ~80 |

## Modified Files (Minimal Changes)

| File | Change | Lines Added |
|------|--------|-------------|
| `intelligent_advisor_api.py` | 3 event emits | ~10 |
| `web/routers/documents.py` | 1 event emit | ~5 |
| `web/routers/scenarios.py` | 1 event emit | ~5 |
| `web/routers/returns.py` | 2 event emits | ~8 |
| `web/templates/partials/sidebar.html` | Include progress bar | ~2 |
| `web/templates/base_modern.html` | Include next-step banner | ~2 |
| `web/app.py` | Register journey router + init event bus | ~15 |
| `config/ai_providers.py` | Delegate to models.py | ~10 |
| `agent/intelligent_tax_agent.py` | Use input guard + prompt files | ~15 |
| `services/ai/unified_ai_service.py` | Provider chain fallback | ~20 |

**Total new:** ~1,325 lines across 13 files
**Total modified:** ~92 lines across 10 files

---

## Build Sequence

1. **Foundation:** Event bus + event types + tests
2. **Orchestrator:** Journey logic + handlers + tests
3. **Security:** Input guard + PII sanitization + cost cap
4. **Config:** Model versions env vars + versioned prompts
5. **API:** Journey endpoints + tests
6. **Frontend:** Progress bar + CTA banner + Alpine store
7. **Integration:** Wire emit calls into existing services
8. **Inline CTAs:** Add connection points within existing pages
9. **Verification:** E2E flow test all 8 journey transitions
