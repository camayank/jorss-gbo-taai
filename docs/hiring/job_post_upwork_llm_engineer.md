# Upwork Job Post — AI/LLM Engineer

**Post to:** Upwork > Web, Mobile & Software Dev > AI & Machine Learning
**Budget:** Hourly, $100–120/hr, estimated 40–50 hours
**Duration:** 6–8 weeks

---

## Title
LLM/AI Engineer — Production Tax Advisor (FastAPI + Anthropic Claude, 6-week contract)

## Description

CA4CPA Global has built a production AI tax advisor for $150K+ earners. It's running on FastAPI (Python 3.11), Anthropic Claude as primary LLM, with Redis + SQLite session persistence and an SSE streaming endpoint.

**Stack:** FastAPI, Anthropic Claude API, AsyncAnthropic, Redis, SQLite, Alpine.js, vanilla JS ES modules

**What's already built:**
- Multi-provider AI routing (Anthropic → OpenAI → Gemini → template fallback)
- 764-rule tax engine (QBI, AMT, NIIT, Schedule C/E/F/H, K-1)
- 82-question adaptive flow engine with scoring and eligibility rules
- SSE streaming endpoint (implemented, needs battle-testing)
- Semantic memory layer (key facts per session injected into prompts)
- Session persistence: Redis + SQLite fallback, 6-month TTL

**5 deliverables (6–8 weeks):**

1. **Streaming — production-ready (Week 1–2)**
   - SSE endpoint battle-tested under realistic conditions
   - Verify chunks arrive in <300ms after first token
   - Handle Anthropic API timeouts (fall back to blocking)
   - Test on iOS Safari + Chrome Android

2. **Persistent semantic memory (Week 2–3)**
   - Facts stored permanently in Redis keyed by session_id
   - Survive session pruning (conversation history truncates; facts must not)

3. **Conversation quality benchmarking (Week 3–4)**
   - Grade 50 real sessions against rubric (right follow-up, IRS code, word count, single question)
   - Output: CSV scorecard + top 10 failure patterns

4. **System prompt A/B framework (Week 4–5)**
   - 2 variants in config/Redis, random session assignment, track completion rate

5. **LLM fallback chain hardening (Week 5–6)**
   - Explicit timeouts per provider, retry logic, provider metrics logging

**Milestone payments:** 25% on streaming sign-off, 25% on memory, 50% on completion.

**NDA required.**

**To apply:**
1. GitHub profile
2. One production LLM integration you shipped (brief description + what you learned)
3. Availability (hours/week) + target rate

---

**Skills:** Python, FastAPI, Anthropic Claude API, LLM Integration, Redis, SSE, AsyncIO
**Category:** AI & Machine Learning > AI Model Integration
**Experience Level:** Expert
