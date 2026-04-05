# AI/LLM Engineer Contract
**Tax Advisor Intelligence Layer — 6–8 Week Engagement**

## The Platform

CA4CPA Global LLC — AI Tax Advisor for $150K+ earners.

**Stack:** FastAPI (Python 3.11), Anthropic Claude (primary), OpenAI GPT-4o (fallback), Redis, SQLite, Alpine.js, vanilla JS ES modules.

**What's already built and working:**
- Multi-provider AI routing (Anthropic → OpenAI → Gemini → Perplexity → template fallback)
- 764-rule tax engine (QBI, AMT, NIIT, Schedule C/E/F/H, K-1)
- 82-question adaptive FlowEngine with scoring and eligibility rules
- Streaming SSE endpoint (`/api/advisor/chat/stream`) — implemented, not battle-tested
- Semantic memory layer — key facts extracted per response, injected into system prompt
- Session persistence: Redis + SQLite fallback, 6-month TTL

## What We Need Built/Hardened

### 1. Streaming — production-ready (Week 1–2)
The SSE endpoint is coded. We need it tested under realistic conditions:
- Verify chunks arrive in <300ms after first token
- Handle Anthropic API timeouts gracefully (fall back to blocking)
- Frontend bubble renders streaming text without flicker
- Test on iOS Safari and Chrome Android

### 2. Persistent semantic memory (Week 2–3)
Currently key facts are re-extracted per request from session profile. We need:
- Facts stored permanently in Redis keyed by `session_id`
- Survive session pruning (conversation history gets truncated; facts must not)
- Format: `{ "filing_status": "married_joint", "total_income": 185000, ... }`
- Injected as structured context into every LLM call

### 3. Conversation quality benchmarking (Week 3–4)
Grade 50 real sessions against a rubric:
- Did the AI ask the right follow-up question?
- Did it cite the right IRS code?
- Did it stay under 180 words?
- Did it end with exactly ONE question?
Output: CSV scorecard + top 10 failure patterns

### 4. System prompt A/B framework (Week 4–5)
Simple mechanism to test 2 system prompt variants:
- Variant A/B stored in config or Redis
- Session randomly assigned on creation
- Track completion rate and question answer rate per variant
- No need for statistical framework — just data collection

### 5. LLM fallback chain hardening (Week 5–6)
Current: Anthropic → OpenAI → template. We need:
- Explicit timeout per provider (Anthropic: 8s, OpenAI: 6s)
- Retry logic: 1 retry on timeout, not on rate limit
- Metrics: log which provider answered each request
- Never show "AI unavailable" to user — always fall back gracefully

## Compensation

- **$100–120/hr**, estimated **40–50 hours** total
- Milestone-based payments (25% on streaming sign-off, 25% on memory, 50% on completion)
- Remote, async-friendly
- NDA required

## How to Apply

Email rakeshanita@gmail.com with:
1. GitHub profile
2. One production LLM integration you shipped (brief description + what you learned)
3. Your availability (hours/week) and target rate

Subject line: **LLM Engineer — [Your Name]**
