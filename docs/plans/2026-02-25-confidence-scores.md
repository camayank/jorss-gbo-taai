# Confidence Scores Visibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface AI confidence levels to users so they know when to trust advice vs. verify with a professional.

**Architecture:** Add response_confidence field to ChatResponse model, calculate based on profile completeness, render visual badges (green/yellow/red) in frontend chat messages.

**Tech Stack:** Python/FastAPI (backend), Pydantic (models), JavaScript/HTML (frontend), pytest (testing)

---

### Task 1: Add Confidence Fields to ChatResponse Model

**Files:**
- Modify: `src/web/intelligent_advisor_api.py:641-644`
- Test: `tests/test_confidence_scores.py`

**Step 1: Write the failing test**

Create `tests/test_confidence_scores.py`:

```python
"""Tests for confidence scores visibility."""

import pytest
from pydantic import ValidationError

from src.web.intelligent_advisor_api import ChatResponse


class TestChatResponseConfidenceFields:
    """Tests for ChatResponse confidence fields."""

    def test_chat_response_has_confidence_field(self):
        """ChatResponse should have response_confidence field."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting",
            response_confidence="high"
        )
        assert response.response_confidence == "high"

    def test_chat_response_has_confidence_reason_field(self):
        """ChatResponse should have confidence_reason field."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting",
            response_confidence="medium",
            confidence_reason="Some profile data missing"
        )
        assert response.confidence_reason == "Some profile data missing"

    def test_chat_response_confidence_defaults_to_high(self):
        """Confidence should default to high."""
        response = ChatResponse(
            session_id="test-123",
            response="Hello",
            response_type="greeting"
        )
        assert response.response_confidence == "high"
        assert response.confidence_reason is None
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_confidence_scores.py::TestChatResponseConfidenceFields -v`
Expected: FAIL with "ValidationError" or "AttributeError" (fields don't exist yet)

**Step 3: Write minimal implementation**

Add to `src/web/intelligent_advisor_api.py` after line 643 (after `requires_professional_review`):

```python
    # Response confidence
    response_confidence: str = "high"  # high, medium, low
    confidence_reason: Optional[str] = None  # Why confidence is reduced
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_confidence_scores.py::TestChatResponseConfidenceFields -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/web/intelligent_advisor_api.py tests/test_confidence_scores.py
git commit -m "feat(confidence): add confidence fields to ChatResponse model"
```

---

### Task 2: Add Confidence Calculation Helper Function

**Files:**
- Modify: `src/web/intelligent_advisor_api.py`
- Test: `tests/test_confidence_scores.py`

**Step 1: Write the failing test**

Add to `tests/test_confidence_scores.py`:

```python
class TestConfidenceCalculation:
    """Tests for confidence calculation logic."""

    def test_high_confidence_with_complete_profile(self):
        """Profile >=70% complete, no complex scenario = high confidence."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.75,
            has_complex_scenario=False
        )
        assert confidence == "high"
        assert reason is None

    def test_medium_confidence_with_partial_profile(self):
        """Profile 40-70% complete = medium confidence."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.55,
            has_complex_scenario=False
        )
        assert confidence == "medium"
        assert "missing" in reason.lower()

    def test_low_confidence_with_minimal_profile(self):
        """Profile <40% complete = low confidence."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.25,
            has_complex_scenario=False
        )
        assert confidence == "low"
        assert reason is not None

    def test_medium_confidence_with_complex_scenario(self):
        """Complex scenario reduces to medium even with complete profile."""
        from src.web.intelligent_advisor_api import calculate_response_confidence

        confidence, reason = calculate_response_confidence(
            profile_completeness=0.80,
            has_complex_scenario=True
        )
        assert confidence == "medium"
        assert "complex" in reason.lower() or "professional" in reason.lower()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_confidence_scores.py::TestConfidenceCalculation -v`
Expected: FAIL with "ImportError" (function doesn't exist)

**Step 3: Write minimal implementation**

Add to `src/web/intelligent_advisor_api.py` after the imports section (around line 50):

```python
def calculate_response_confidence(
    profile_completeness: float,
    has_complex_scenario: bool = False
) -> tuple:
    """
    Calculate confidence level for a response based on data quality.

    Args:
        profile_completeness: 0.0 to 1.0 indicating how complete the profile is
        has_complex_scenario: True if complex tax situation detected

    Returns:
        tuple of (confidence_level, reason)
    """
    if profile_completeness >= 0.70 and not has_complex_scenario:
        return ("high", None)
    elif profile_completeness >= 0.40:
        if has_complex_scenario:
            return ("medium", "Complex tax situation - verify with professional")
        return ("medium", "Some profile data missing")
    else:
        return ("low", "Limited data available - estimates may vary significantly")
```

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_confidence_scores.py::TestConfidenceCalculation -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/web/intelligent_advisor_api.py tests/test_confidence_scores.py
git commit -m "feat(confidence): add confidence calculation helper function"
```

---

### Task 3: Update API Responses to Include Confidence

**Files:**
- Modify: `src/web/intelligent_advisor_api.py` (multiple ChatResponse returns)

**Step 1: Identify ChatResponse returns for calculation/strategy types**

Search for `return ChatResponse(` in the file and identify ones with:
- `response_type="calculation"`
- `response_type="strategy"`
- `response_type="report"`

**Step 2: Update calculation response (around line 4850)**

Find the calculation response and add confidence:

```python
# Calculate confidence
confidence, confidence_reason = calculate_response_confidence(
    profile_completeness=chat_engine.calculate_profile_completeness(profile),
    has_complex_scenario=should_require_professional_review(profile)
)

return ChatResponse(
    session_id=request.session_id,
    response=response_text,
    response_type="calculation",
    response_confidence=confidence,
    confidence_reason=confidence_reason,
    # ... other existing fields
)
```

**Step 3: Update strategy responses similarly**

Find strategy responses and add the same confidence calculation.

**Step 4: Verify syntax**

Run: `python3 -c "from src.web.intelligent_advisor_api import intelligent_chat; print('OK')"`
Expected: OK (no import errors)

**Step 5: Commit**

```bash
git add src/web/intelligent_advisor_api.py
git commit -m "feat(confidence): add confidence to calculation and strategy responses"
```

---

### Task 4: Add Frontend Confidence Badge Renderer

**Files:**
- Modify: `src/web/templates/intelligent_advisor.html`

**Step 1: Find the message rendering JavaScript**

Look for `function renderMessage` or similar in the template.

**Step 2: Add confidence badge render function**

Add this JavaScript function in the `<script>` section:

```javascript
function renderConfidenceBadge(confidence, reason) {
    if (!confidence || confidence === 'high') {
        // Don't show badge for high confidence (default)
        return '';
    }

    const badges = {
        high: { icon: '\u{1F7E2}', label: 'High Confidence', class: 'confidence-high' },
        medium: { icon: '\u{1F7E1}', label: 'Moderate Confidence', class: 'confidence-medium' },
        low: { icon: '\u{1F534}', label: 'Limited Data', class: 'confidence-low' }
    };

    const badge = badges[confidence] || badges.medium;
    const tooltipAttr = reason ? ` title="${reason}"` : '';

    return `<div class="confidence-badge ${badge.class}"${tooltipAttr}>
        <span class="confidence-icon">${badge.icon}</span>
        <span class="confidence-label">${badge.label}</span>
        ${reason ? `<span class="confidence-reason">${reason}</span>` : ''}
    </div>`;
}
```

**Step 3: Update message rendering to include badge**

Find where AI messages are rendered and add:

```javascript
// Add confidence badge for calculation/strategy responses
if (data.response_type === 'calculation' || data.response_type === 'strategy' || data.response_type === 'report') {
    messageHtml += renderConfidenceBadge(data.response_confidence, data.confidence_reason);
}
```

**Step 4: Add/verify CSS styles**

Ensure these styles exist (they should already be in the file):

```css
.confidence-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.85rem;
    margin-top: 12px;
}

.confidence-badge.confidence-high {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
}

.confidence-badge.confidence-medium {
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
}

.confidence-badge.confidence-low {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
}

.confidence-reason {
    font-size: 0.8rem;
    opacity: 0.8;
    margin-left: 4px;
}
```

**Step 5: Commit**

```bash
git add src/web/templates/intelligent_advisor.html
git commit -m "feat(confidence): add frontend confidence badge rendering"
```

---

### Task 5: Run Full Test Suite and Verify

**Files:**
- None (verification only)

**Step 1: Run confidence tests**

Run: `python3 -m pytest tests/test_confidence_scores.py -v`
Expected: All tests PASS (7 tests)

**Step 2: Run related API tests**

Run: `python3 -m pytest tests/ -k "advisor" -v --tb=short 2>&1 | tail -30`
Expected: No new regressions

**Step 3: Manual verification (if server running)**

1. Start the server
2. Open intelligent advisor chat
3. Enter minimal data and verify "Limited Data" badge appears
4. Complete profile and verify badge disappears or shows "High Confidence"

**Step 4: Commit verification**

```bash
git add -A
git commit -m "chore(confidence): verify all tests pass" --allow-empty
```

---

### Task 6: Update Documentation

**Files:**
- Modify: `docs/plans/2026-02-25-confidence-scores-design.md`

**Step 1: Update status**

Change line 4 from:
```markdown
**Status:** Approved
```
To:
```markdown
**Status:** Implemented
```

**Step 2: Commit**

```bash
git add docs/plans/2026-02-25-confidence-scores-design.md
git commit -m "docs: mark confidence scores design as implemented"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add confidence fields to ChatResponse | intelligent_advisor_api.py, test file |
| 2 | Add confidence calculation helper | intelligent_advisor_api.py |
| 3 | Update API responses with confidence | intelligent_advisor_api.py |
| 4 | Add frontend confidence badge | intelligent_advisor.html |
| 5 | Run full test suite | Verification |
| 6 | Update documentation | Design doc |

**Total: 6 tasks, ~120 lines of code**
