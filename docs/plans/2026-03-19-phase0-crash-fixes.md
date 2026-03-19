# Phase 0: Stop the Advisor from Crashing — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the 7 bugs that prevent the AI Tax Advisor from functioning at all on Render.

**Architecture:** Surgical single-line or few-line edits to existing code. No new files, no refactoring, no feature changes. Every fix is a guard, a variable rename, or a condition fix.

**Tech Stack:** Python (FastAPI, Pydantic), all changes in `src/web/intelligent_advisor_api.py` and `src/security/session_token.py`

---

### Task 1: Fix `get_ai_metrics_service` None call (W2)

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:2917`
- Modify: `src/web/intelligent_advisor_api.py:4367` (second occurrence)

**Step 1: Fix line 2917**

Find:
```python
        metrics = get_ai_metrics_service()
```

Replace with:
```python
        metrics = get_ai_metrics_service() if get_ai_metrics_service else None
```

Then on line 2923 where `metrics.record_response_quality(` is called, wrap it:
```python
            if metrics:
                metrics.record_response_quality(
```

Find the closing `)` of that call and ensure the `if metrics:` block is properly indented.

**Step 2: Fix line 4367 (second occurrence)**

Search for the other `get_ai_metrics_service()` call. Apply the same guard:
```python
        if get_ai_metrics_service:
            get_ai_metrics_service().record_response_quality(...)
```

**Step 3: Verify module imports**

```bash
PYTHONPATH=".:src" .venv/bin/python3 -c "from web.intelligent_advisor_api import chat_engine; print('OK')"
```

**Step 4: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix: guard get_ai_metrics_service against None when metrics_service not installed"
```

---

### Task 2: Fix `message` undefined in comparison (W3)

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:5085`

**Step 1: Fix the variable name**

Find at line 5085:
```python
                question=message,
```

Replace with:
```python
                question=msg_original,
```

`msg_original` is defined at line 4110 and is the sanitized user message.

**Step 2: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix: use msg_original instead of undefined message in scenario comparison"
```

---

### Task 3: Fix InputGuard response field names (W4)

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:4127-4135`

**Step 1: Fix the ChatResponse constructor**

Find:
```python
            return ChatResponse(
                session_id=request.session_id,
                message="I can only help with tax-related questions. Could you please rephrase your question about your tax situation?",
                quick_actions=[
                    {"label": "What deductions can I claim?", "value": "ask_deductions"},
                    {"label": "Help me file my taxes", "value": "start_filing"},
                ],
                profile=profile,
            )
```

Replace with:
```python
            return ChatResponse(
                session_id=request.session_id,
                response="I can only help with tax-related questions. Could you please rephrase your question about your tax situation?",
                response_type="redirect",
                quick_actions=[
                    {"label": "What deductions can I claim?", "value": "ask_deductions"},
                    {"label": "Help me file my taxes", "value": "start_filing"},
                ],
            )
```

Changes: `message=` → `response=`, added `response_type="redirect"`, removed `profile=profile` (not a ChatResponse field).

**Step 2: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix: use correct ChatResponse field names in InputGuard block"
```

---

### Task 4: Fix `has_basics` falsy on $0 income (W8)

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:5102`

**Step 1: Fix the condition**

Find:
```python
    has_basics = profile.get("total_income") and profile.get("filing_status") and profile.get("state")
```

Replace with:
```python
    has_basics = profile.get("total_income") is not None and profile.get("filing_status") and profile.get("state")
```

This changes only the first operand. `is not None` returns `True` for `0`, `""`, and any other value — only `None` (meaning the field was never set) returns `False`.

**Step 2: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix: allow zero income in has_basics check (is not None instead of truthy)"
```

---

### Task 5: Fix HSA `or True` always-recommend (W6)

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:2618`

**Step 1: Fix the condition**

Find:
```python
        if profile.get("hsa_contributions") is not None or True:  # Assume eligible
```

Replace with:
```python
        if profile.get("hsa_contributions") is not None or profile.get("has_hsa") or profile.get("income_type") in ("w2_employee", "self_employed"):
```

This recommends HSA only when: user explicitly mentioned HSA contributions, OR user said they have an HSA, OR they're employed/self-employed (where HDHP enrollment is plausible). Retirees and passive-income-only users won't get the recommendation.

**Step 2: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix: remove or-True from HSA condition — recommend only for plausible eligible users"
```

---

### Task 6: Fix filing status map for married (W7)

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:2506`

**Step 1: Fix the comparison**

Find:
```python
        if filing_status in ["married_filing_jointly", "married filing jointly"]:
```

Replace with:
```python
        if filing_status in ["married_joint", "married_filing_jointly", "married filing jointly"]:
```

Adding `"married_joint"` (the value actually stored in the session profile) to the list. Keeps the other two for backward compatibility.

**Step 2: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix: add married_joint to IRA filing status check (actual stored value)"
```

---

### Task 7: Fix session token mismatch (W1)

This is the root cause of the session error loop. The fix has two parts:

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:1148-1160` (get_or_create_session)
- Modify: `src/web/static/js/advisor/modules/advisor-core.js:629-653` (initializeSession)

**Step 1: Make chat engine reuse the sessions_api token**

In `get_or_create_session()`, when creating a new session (the block starting at line 1148), before generating a new token, check if the session already exists in the SQLite persistence store and extract its token:

Find the line inside get_or_create_session that creates the new session token:
```python
                SESSION_TOKEN_KEY: generate_session_token(),
```

Replace the entire new_session block construction to first try loading from the sessions_api persistence:

```python
            # Try to recover token from sessions_api persistence before generating a new one
            existing_token = None
            if self._sqlite_persistence:
                try:
                    existing_record = self._sqlite_persistence.load_session(session_id)
                    if existing_record and existing_record.data:
                        data = existing_record.data if isinstance(existing_record.data, dict) else {}
                        existing_token = data.get(SESSION_TOKEN_KEY)
                except Exception:
                    pass

            new_session = {
                "id": session_id,
                "created_at": datetime.now(),
                "profile": {},
                "conversation": [],
                "state": "greeting",
                "calculations": None,
                "strategies": [],
                "lead_score": 0,
                SESSION_TOKEN_KEY: existing_token or generate_session_token(),
```

This way if `sessions_api` already created the session with Token A, the chat engine reuses Token A instead of generating Token B.

**Step 2: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix: reuse sessions_api token in chat engine to prevent token mismatch on second message"
```

---

### Task 8: Final verification

**Step 1: Verify module loads**

```bash
PYTHONPATH=".:src" .venv/bin/python3 -c "from web.intelligent_advisor_api import chat_engine; print('OK')"
```

**Step 2: Test session creation + chat locally**

```bash
# Create session
SESSION=$(curl -s -X POST http://127.0.0.1:8000/api/sessions/create-session \
  -H "Content-Type: application/json" \
  -d '{"workflow_type":"intelligent_conversational","tax_year":2025}')
echo $SESSION

# Extract session_id and token
SID=$(echo $SESSION | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
TOK=$(echo $SESSION | python3 -c "import sys,json; print(json.load(sys.stdin)['session_token'])")

# First message
curl -s -X POST http://127.0.0.1:8000/api/advisor/chat \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: $TOK" \
  -d "{\"session_id\":\"$SID\",\"message\":\"I'm single with 85k income\"}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response','')[:200])"

# Second message (this is where token mismatch would cause 403)
curl -s -X POST http://127.0.0.1:8000/api/advisor/chat \
  -H "Content-Type: application/json" \
  -H "X-Session-Token: $TOK" \
  -d "{\"session_id\":\"$SID\",\"message\":\"I live in California\"}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response','')[:200])"
```

Both messages should return valid responses, not 403 or "session_error".

**Step 3: Push to GitHub**

```bash
git push origin main
```

Then redeploy on Render.
