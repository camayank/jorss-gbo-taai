# Critical Bug Fixes — Intelligent Advisor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 5 critical app-breaking bugs in the Intelligent Advisor chat flow that prevent name/email/income capture, cause typing indicator hangs, missing CSRF tokens, and health endpoint crashes.

**Architecture:** Direct fixes in existing files — no new modules. C1 is fixed by replacing inline event handlers with post-render addEventListener calls. C2 hoists timer variables. C3 adds CSRF to fetchWithRetry. C5 fixes the attribute name.

**Tech Stack:** Vanilla JS (intelligent-advisor.js), Python/FastAPI (intelligent_advisor_api.py)

---

### Task 1: Fix C1 — DOMPurify strips inline event handlers (name/email/income capture broken)

**Files:**
- Modify: `src/web/static/js/pages/intelligent-advisor.js:2931-2951` (name + email capture)
- Modify: `src/web/static/js/pages/intelligent-advisor.js:3280-3288` (income capture)
- Modify: `src/web/static/js/pages/intelligent-advisor.js:6600-6609` (income correction)

**Problem:** DOMPurify sanitizes AI messages (line 2127-2138) and strips `onclick`/`onkeypress` attributes because they're not in `ALLOWED_ATTR`. The name, email, and income capture forms use inline handlers that get silently removed.

**Fix approach:** Remove inline event handlers from the HTML strings. After `addMessage()` renders the HTML, use `getElementById` + `addEventListener` to attach the handlers. This is more secure than whitelisting event handlers in DOMPurify.

**Step 1: Fix name capture (lines 2931-2938)**

Replace the inline handlers with clean HTML, then attach listeners after render:

```javascript
// OLD (line 2936):
addMessage('ai', `Perfect! Please enter your full name below so I can personalize your tax advisory report.<br><br><input type="text" id="nameInput" placeholder="Your full name" style="..." onkeypress="if(event.key==='Enter') captureName()"><br><button onclick="captureName()" style="...">Continue →</button>`);

// NEW:
addMessage('ai', `Perfect! Please enter your full name below so I can personalize your tax advisory report.<br><br><input type="text" id="nameInput" placeholder="Your full name" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);"><br><button id="nameSubmitBtn" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Continue →</button>`);
setTimeout(() => {
  const nameEl = document.getElementById('nameInput');
  const nameBtn = document.getElementById('nameSubmitBtn');
  if (nameEl) {
    nameEl.addEventListener('keypress', function(e) { if (e.key === 'Enter') captureName(); });
    nameEl.focus();
  }
  if (nameBtn) nameBtn.addEventListener('click', function() { captureName(); });
}, 100);
```

**Step 2: Fix email capture (lines 2945-2952)**

Same pattern — remove inline handlers, attach with addEventListener:

```javascript
// NEW:
addMessage('ai', `Great! Please enter your email address below.<br><br><input type="email" id="emailInput" placeholder="your.email@example.com" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);"><br><button id="emailSubmitBtn" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Continue →</button>`);
setTimeout(() => {
  const emailEl = document.getElementById('emailInput');
  const emailBtn = document.getElementById('emailSubmitBtn');
  if (emailEl) {
    emailEl.addEventListener('keypress', function(e) { if (e.key === 'Enter') captureEmail(); });
    emailEl.focus();
  }
  if (emailBtn) emailBtn.addEventListener('click', function() { captureEmail(); });
}, 100);
```

**Step 3: Fix income capture (line 3285)**

```javascript
// NEW:
addMessage('ai', `Please enter your total annual income for 2025:<br><br><input type="number" id="incomeInput" placeholder="Enter amount" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);"><br><button id="incomeSubmitBtn" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Continue →</button>`);
setTimeout(() => {
  const incomeEl = document.getElementById('incomeInput');
  const incomeBtn = document.getElementById('incomeSubmitBtn');
  if (incomeEl) {
    incomeEl.addEventListener('keypress', function(e) { if (e.key === 'Enter') captureIncome(); });
    incomeEl.focus();
  }
  if (incomeBtn) incomeBtn.addEventListener('click', function() { captureIncome(); });
}, 100);
```

**Step 4: Fix income correction (line 6607)**

```javascript
// NEW:
addMessage('ai', `What's your correct total annual income?<br><br><input type="number" id="incomeInput" placeholder="Enter amount" style="width: 100%; padding: var(--space-3-5); margin: var(--space-3) 0; background: rgba(255,255,255,0.05); border: 2px solid var(--border); border-radius: var(--radius-lg); color: var(--text); font-size: var(--text-base);"><br><button id="incomeSubmitBtn" style="padding: var(--space-3) var(--space-8); background: var(--primary); color: white; border: none; border-radius: var(--radius-lg); cursor: pointer; font-weight: var(--font-semibold); margin-top: var(--space-2);">Update Income</button>`);
setTimeout(() => {
  const incomeEl = document.getElementById('incomeInput');
  const incomeBtn = document.getElementById('incomeSubmitBtn');
  if (incomeEl) {
    incomeEl.addEventListener('keypress', function(e) { if (e.key === 'Enter') captureIncome(); });
    incomeEl.focus();
  }
  if (incomeBtn) incomeBtn.addEventListener('click', function() { captureIncome(); });
}, 100);
```

**Step 5: Commit**

```bash
git add src/web/static/js/pages/intelligent-advisor.js
git commit -m "fix(critical): replace inline event handlers stripped by DOMPurify with addEventListener

DOMPurify sanitization was silently removing onclick/onkeypress attributes
from name, email, and income capture forms. Users could see the inputs
but clicking Continue did nothing. Now using addEventListener after render."
```

---

### Task 2: Fix C2 — Timer variables scoped inside try, referenced in catch

**Files:**
- Modify: `src/web/static/js/pages/intelligent-advisor.js:7211-7424`

**Problem:** `let thinkingTimer` and `let extendedTimer` are declared inside a try block. If an error occurs before they're assigned, `clearTimeout()` in the catch block would fail. More critically, if an error occurs during the `setTimeout` calls themselves, the variables may be undefined when catch tries to clear them.

**Step 1: Hoist timer declarations above try block**

Find the code around line 7211 (inside the `sendMessage` function try block). The timers are declared at lines 7212 and 7216. Hoist them before the try:

```javascript
// BEFORE (inside try block):
        // Show extended "Thinking..." indicator for AI responses (may take longer)
        let thinkingTimer = setTimeout(() => {

// AFTER (before try block, add these two lines):
        let thinkingTimer = null;
        let extendedTimer = null;

        // Then inside the try block, change to assignments (not declarations):
        thinkingTimer = setTimeout(() => {
          const typingEl = document.querySelector('.typing-indicator .typing-text');
          if (typingEl) typingEl.textContent = 'Thinking deeply...';
        }, 4000);
        extendedTimer = setTimeout(() => {
          const typingEl = document.querySelector('.typing-indicator .typing-text');
          if (typingEl) typingEl.textContent = 'Taking a bit longer than usual, still working...';
        }, 12000);
```

The catch block (line 7422-7424) already has `clearTimeout(thinkingTimer)` and `clearTimeout(extendedTimer)` — those will now safely reference the hoisted variables (`clearTimeout(null)` is a no-op).

**Step 2: Commit**

```bash
git add src/web/static/js/pages/intelligent-advisor.js
git commit -m "fix(critical): hoist timer variables above try-catch to prevent ReferenceError

thinkingTimer and extendedTimer were declared with let inside try block.
If error occurred before assignment, catch block clearTimeout would fail.
Now declared before try with null initialization."
```

---

### Task 3: Fix C3 — fetchWithRetry missing CSRF token

**Files:**
- Modify: `src/web/static/js/pages/intelligent-advisor.js:6980-6999`

**Problem:** The `fetchWithRetry()` function (line 6980) is used for all main chat API calls but doesn't include CSRF tokens. There's already a `fetchWithRetryRobust()` (line 580) that does include CSRF, but the main chat flow uses the insecure `fetchWithRetry()`. 10+ POST endpoints are affected.

**Fix:** Add CSRF token handling to `fetchWithRetry()` to match what `fetchWithRetryRobust()` already does. The `getCSRFToken()` function already exists at line 244.

**Step 1: Add CSRF token to fetchWithRetry**

In `fetchWithRetry()` (line 6980), after the session token merge (line 6988-6993), add CSRF token handling:

```javascript
    async function fetchWithRetry(url, options, maxRetries = 3) {
      let lastError;

      for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

          // Add session token for advisor API requests
          const sessionToken = sessionStorage.getItem('advisor_session_token');
          const mergedHeaders = { ...options.headers };
          if (sessionToken && url.includes('/api/advisor/')) {
              mergedHeaders['X-Session-Token'] = sessionToken;
          }

          // SECURITY: Add CSRF token for state-changing requests
          const method = (options.method || 'GET').toUpperCase();
          if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
            const csrfToken = getCSRFToken();
            if (csrfToken) {
              mergedHeaders['X-CSRF-Token'] = csrfToken;
            }
          }

          const response = await fetch(url, {
            ...options,
            signal: controller.signal,
            headers: mergedHeaders,
            credentials: 'same-origin'
          });
```

**Step 2: Commit**

```bash
git add src/web/static/js/pages/intelligent-advisor.js
git commit -m "fix(critical): add CSRF token to fetchWithRetry for all POST requests

fetchWithRetry was missing X-CSRF-Token header on 10+ POST endpoints
including /api/advisor/chat. All chat and report requests would be
rejected if CSRF middleware is enforced. Now matches fetchWithRetryRobust."
```

---

### Task 4: Fix C5 — Health endpoint crashes on non-existent _persistence attribute

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:2885`

**Problem:** Health endpoint accesses `chat_engine._persistence` which doesn't exist. The `IntelligentChatEngine` class (line 769) defines `self._redis_persistence` and `self._sqlite_persistence`, but never `self._persistence`. This causes an `AttributeError` on every health check call.

**Step 1: Fix the attribute reference**

Change line 2885 from:
```python
"persistence_enabled": chat_engine._persistence is not None,
```

To:
```python
"persistence_enabled": chat_engine._sqlite_persistence is not None or chat_engine._redis_persistence is not None,
```

**Step 2: Verify the fix**

Run: `python -c "from web.intelligent_advisor_api import chat_engine; print(hasattr(chat_engine, '_sqlite_persistence'), hasattr(chat_engine, '_redis_persistence'))"`
Expected: `True True`

**Step 3: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "fix(critical): health endpoint references non-existent _persistence attribute

chat_engine._persistence was never defined — should check _sqlite_persistence
and _redis_persistence which are the actual L2 persistence layer attributes.
Health endpoint was returning 500 on every call."
```

---

### Task 5: Verification & Final Commit

**Step 1: Verify no syntax errors in JS**

Run: `node --check src/web/static/js/pages/intelligent-advisor.js`
Expected: No output (clean syntax)

**Step 2: Verify no syntax errors in Python**

Run: `python -m py_compile src/web/intelligent_advisor_api.py`
Expected: No output (clean syntax)

**Step 3: Search for any remaining inline handlers in addMessage calls**

Run: `grep -n 'onclick\|onkeypress\|onchange' src/web/static/js/pages/intelligent-advisor.js`
Expected: No results in addMessage() strings. May appear in other contexts (e.g., non-sanitized elements) which is fine.

**Step 4: Verify CSRF token is now in fetchWithRetry**

Run: `grep -A3 'CSRF' src/web/static/js/pages/intelligent-advisor.js | head -20`
Expected: See CSRF token handling in both `fetchWithRetryRobust` and `fetchWithRetry`

**Step 5: Final combined verification commit (if all checks pass)**

```bash
git log --oneline -5  # Verify the 4 fix commits are there
```
