# Confidence Scores Visibility Design Document

**Date:** 2026-02-25
**Status:** Implemented
**Approach:** Response-Level Confidence (Approach A)

## Overview

Surface AI confidence levels to users so they know when to trust advice vs. verify with a professional. Currently, all AI responses appear equally confident, leading users to act on uncertain information without verification.

## Problem

The SWOT analysis identified "Confidence Scores Hidden from Users" as a Risk 8/10 issue:
- Backend has confidence tracking (HIGH/MEDIUM/LOW via `ConfidenceLevel` enum)
- Frontend has CSS for confidence badges (unused)
- `ChatResponse` doesn't include confidence data
- Users can't distinguish certain vs uncertain advice

## Design

### Backend Changes

**File: `src/web/intelligent_advisor_api.py`**

Add fields to `ChatResponse` model (after line 643):

```python
# Response confidence
response_confidence: str = "high"  # high, medium, low
confidence_reason: Optional[str] = None  # Why confidence is reduced
```

Add helper function to calculate response confidence:

```python
def calculate_response_confidence(profile_completeness: float, has_complex_scenario: bool) -> tuple[str, Optional[str]]:
    """
    Calculate confidence level for a response based on data quality.

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

Update all `ChatResponse` returns to include confidence:

```python
return ChatResponse(
    session_id=request.session_id,
    response=response_text,
    response_type="calculation",
    response_confidence=confidence,
    confidence_reason=reason,
    # ... other fields
)
```

### Frontend Changes

**File: `src/web/templates/intelligent_advisor.html`**

Update `renderMessage()` function to show confidence badge:

```javascript
function renderConfidenceBadge(confidence, reason) {
    const badges = {
        high: { icon: '🟢', label: 'High Confidence', class: 'confidence-high' },
        medium: { icon: '🟡', label: 'Moderate Confidence', class: 'confidence-medium' },
        low: { icon: '🔴', label: 'Limited Data', class: 'confidence-low' }
    };

    const badge = badges[confidence] || badges.high;
    const tooltip = reason ? ` title="${reason}"` : '';

    return `<div class="confidence-badge ${badge.class}"${tooltip}>
        <span class="confidence-icon">${badge.icon}</span>
        <span class="confidence-label">${badge.label}</span>
    </div>`;
}
```

Add badge to AI message rendering (only for calculation/strategy responses):

```javascript
if (data.response_type === 'calculation' || data.response_type === 'strategy') {
    messageHtml += renderConfidenceBadge(data.response_confidence, data.confidence_reason);
}
```

### Visual Design

```
┌─────────────────────────────────────────────────────┐
│ 🤖 Based on your information, here's your estimate: │
│                                                     │
│ Estimated Federal Tax: $15,234                      │
│ Potential Savings: $3,500                           │
│                                                     │
│ 🟢 High Confidence                                  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🤖 Here are some tax-saving strategies:             │
│                                                     │
│ • Max out 401(k) - save $2,200                      │
│ • HSA contribution - save $800                      │
│                                                     │
│ 🟡 Moderate Confidence                              │
│    ⓘ Some profile data missing                      │
└─────────────────────────────────────────────────────┘
```

### Confidence Thresholds

| Level | Profile Completeness | Complex Scenario | Visual |
|-------|---------------------|------------------|--------|
| HIGH | ≥70% | No | 🟢 Green |
| MEDIUM | 40-70% | Any | 🟡 Amber |
| MEDIUM | ≥70% | Yes | 🟡 Amber |
| LOW | <40% | Any | 🔴 Red |

### When to Show

Show confidence badge on:
- `response_type="calculation"` - Tax estimates
- `response_type="strategy"` - Recommendations
- `response_type="report"` - Full analysis

Don't show on:
- `response_type="greeting"` - Initial greeting
- `response_type="question"` - Data collection questions

## Testing Strategy

**File: `tests/test_confidence_scores.py`**

```python
class TestResponseConfidence:
    def test_high_confidence_with_complete_profile(self):
        """Profile >70% complete, no complex scenario = high confidence."""

    def test_medium_confidence_with_partial_profile(self):
        """Profile 40-70% complete = medium confidence."""

    def test_low_confidence_with_minimal_profile(self):
        """Profile <40% complete = low confidence."""

    def test_medium_confidence_with_complex_scenario(self):
        """Complex scenario reduces to medium even with complete profile."""

    def test_chat_response_includes_confidence_fields(self):
        """ChatResponse model has response_confidence and confidence_reason."""
```

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/web/intelligent_advisor_api.py` | Modify | ~40 |
| `src/web/templates/intelligent_advisor.html` | Modify | ~30 |
| `tests/test_confidence_scores.py` | Create | ~50 |

**Total: ~120 lines**

## Out of Scope

- Field-level confidence (per extracted value) - future iteration
- Confidence for document extraction (separate system)
- Confidence history/trending
- User feedback on confidence accuracy

## Approval

- [x] Backend design approved
- [x] Frontend design approved
- [x] Testing strategy approved
- [x] Complete design approved

Ready for implementation planning.
