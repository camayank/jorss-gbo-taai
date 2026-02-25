# Liability Disclaimers Design Document

**Date:** 2026-02-25
**Status:** Approved
**Approach:** Hybrid (Frontend Session Banner + Backend Response Field)

## Overview

Add liability disclaimers throughout the tax advisory platform to protect against legal liability. Users must acknowledge disclaimers before interacting with the AI, and all advisory responses include context-sensitive disclaimer text.

## Problem

The SWOT analysis identified missing liability disclaimers as a critical gap (Risk: 9/10):
- API greeting in `intelligent_advisor_api.py` has no disclaimer
- No user acknowledgment mechanism before receiving AI advice
- ChatResponse model has no field for disclaimer text
- Users may perceive AI responses as professional tax advice

## Design

### 1. Frontend Session Banner

A dismissible banner shown at the top of the chat interface when a session starts.

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️  IMPORTANT: AI Tax Information Disclaimer                    │
│                                                                 │
│ This AI assistant provides general tax information only.        │
│ • I am NOT a licensed CPA, EA, or tax professional             │
│ • This is NOT professional tax advice                          │
│ • Consult a licensed professional for your specific situation  │
│                                                                 │
│                                      [ I Understand ]          │
└─────────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Appears when chat page loads (before any interaction)
- Chat input disabled until user clicks "I Understand"
- Stored in `sessionStorage` (clears when browser tab closes)
- Amber background (#fffbeb) with amber border (#f59e0b) matching existing disclaimer pattern

**File:** `src/web/templates/intelligent_advisor.html`

### 2. Backend ChatResponse Model Enhancement

Add disclaimer fields to `ChatResponse` model.

**New Fields:**
```python
class ChatResponse(BaseModel):
    # ... existing fields ...

    # Liability disclaimer fields
    disclaimer: Optional[str] = None
    requires_professional_review: bool = False
```

**Disclaimer Logic:**
| Response Type | Include Disclaimer | requires_professional_review |
|--------------|-------------------|------------------------------|
| Greeting | Always | False |
| Strategy recommendations | Always | False |
| Savings estimates | Always | False |
| Complex scenarios* | Always | True |
| Simple Q&A | Optional | False |

*Complex scenarios: income >$200K, multi-state, crypto, foreign income, passive losses

**Standard Disclaimer Constant:**
```python
STANDARD_DISCLAIMER = (
    "This is AI-generated information for educational purposes only, "
    "not professional tax advice. Consult a licensed CPA or EA for "
    "your specific situation."
)
```

**File:** `src/web/intelligent_advisor_api.py`

### 3. API Greeting Disclaimer

Update the greeting in `intelligent_advisor_api.py` (line ~4060).

**New Greeting:**
```python
greeting_response = """Hello! I'm your AI tax advisor.

⚠️ **Important:** I provide general tax information only—not professional tax advice. For your specific situation, consult a licensed CPA or EA.

I can help you:
• **Estimate your taxes** for 2025
• **Find tax savings** opportunities
• **Generate professional reports**

To get started, what's your filing status?"""
```

**File:** `src/web/intelligent_advisor_api.py` (line ~4060)

## Testing Strategy

**New file:** `tests/test_liability_disclaimers.py`

| Test | Description |
|------|-------------|
| `test_session_banner_blocks_input` | Chat input disabled until "I Understand" clicked |
| `test_chat_response_includes_disclaimer` | Verify `disclaimer` field populated for strategy responses |
| `test_greeting_has_disclaimer` | API greeting includes disclaimer text |
| `test_complex_scenario_flags_professional` | `requires_professional_review=True` for complex scenarios |

## Files Changed

| File | Action | Estimated Lines |
|------|--------|-----------------|
| `src/web/templates/intelligent_advisor.html` | Modify | ~50 |
| `src/web/intelligent_advisor_api.py` | Modify | ~30 |
| `tests/test_liability_disclaimers.py` | Create | ~80 |

**Total: ~160 lines**

## Out of Scope

- Persistent checkbox acceptance (localStorage) - using session-only
- Full terms modal with scroll requirement
- Modifications to existing disclaimer.html or terms.html pages
- Email/notification disclaimers

## Approval

- [x] Frontend session banner design approved
- [x] Backend ChatResponse enhancement approved
- [x] API greeting disclaimer approved
- [x] Testing strategy approved
- [x] Complete design approved

Ready for implementation planning.
