# PM Critical 7: Must-Have Flow Improvements

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the 7 must-have gaps identified by senior PM review so a CPA demo produces correct, credible numbers.

**Architecture:** Add new questions to both client (advisor-flow.js) and server (_get_dynamic_next_question) question engines, add EITC + withholding estimation to _fallback_calculation, restructure calculation response to lead with refund/owed.

**Tech Stack:** Python (FastAPI), JavaScript (ES modules), no new dependencies.

---

### Task 1: Add Qualifying Surviving Spouse to filing status

Files: `src/web/static/js/advisor/modules/advisor-flow.js`, `src/web/intelligent_advisor_api.py`

### Task 2: Add federal withholding question + auto-estimate

Files: `src/web/intelligent_advisor_api.py` (_get_dynamic_next_question + _score_next_questions + _quick_action_map + _fallback_calculation)

### Task 3: Add dependent age split (under 17 vs 17+)

Files: `src/web/intelligent_advisor_api.py` (_get_dynamic_next_question + _quick_action_map + _fallback_calculation CTC)

### Task 4: Add EITC to _fallback_calculation

Files: `src/web/intelligent_advisor_api.py` (_fallback_calculation)

### Task 5: Show running estimate after each Phase 2 answer

Files: `src/web/intelligent_advisor_api.py` (response building in /chat endpoint)

### Task 6: Lead calculation result with refund/owed

Files: `src/web/intelligent_advisor_api.py` (response text building)

### Task 7: Make report the natural conclusion

Files: `src/web/intelligent_advisor_api.py` (post-calculation response + quick_actions ordering)
