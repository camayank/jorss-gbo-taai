# Circular 230 Compliance (MVP) Design Document

**Date:** 2026-02-25
**Status:** Approved
**Approach:** User Acknowledgment + Scope Limitations (MVP)

## Overview

Add IRS Circular 230 compliance safeguards to protect users and limit liability. MVP focuses on user acknowledgment and scope limitations rather than full engagement letter system.

## Problem

The SWOT analysis identified "No IRS Circular 230 Compliance" as a Risk 9/10 issue:
- No engagement letter requirement
- No written scope of work
- No conflict-of-interest disclosure
- System provides tax guidance without required professional safeguards

## MVP Design

### Backend Changes

**File: `src/web/intelligent_advisor_api.py`**

Add consent tracking to session management:

```python
class ProfessionalAcknowledgment(BaseModel):
    """Track user acknowledgment of professional standards limitations."""
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
```

Add acknowledgment check to chat endpoint:

```python
def check_acknowledgment(session_id: str) -> bool:
    """Check if user has acknowledged professional standards."""
    # Return True if acknowledged, False if needs acknowledgment
```

Add new endpoint:

```python
@router.post("/acknowledge-standards")
async def acknowledge_standards(request: AcknowledgmentRequest):
    """Record user acknowledgment of professional standards limitations."""
```

### Frontend Changes

**File: `src/web/templates/intelligent_advisor.html`**

Add acknowledgment modal that appears on first use:

```javascript
function showProfessionalAcknowledgment() {
    // Modal with:
    // - Title: "Important: Professional Standards Notice"
    // - Content explaining this is not professional tax advice
    // - Checkbox: "I understand this tool provides estimates only"
    // - Checkbox: "I understand I should consult a tax professional"
    // - Button: "I Acknowledge and Continue"
}
```

Add scope limitation banner to chat interface:

```html
<div class="scope-banner">
    This tool provides tax estimates and educational information only.
    It is not a substitute for professional tax advice.
</div>
```

### Acknowledgment Text

```
PROFESSIONAL STANDARDS NOTICE

This tax advisory tool provides estimates and educational information only.
By using this tool, you acknowledge and agree that:

1. This is NOT professional tax advice
2. This tool is NOT a licensed CPA, EA, or tax attorney
3. Calculations are estimates that may not reflect your actual tax liability
4. You should consult a qualified tax professional before filing
5. You are responsible for the accuracy of information you provide
6. Tax laws change frequently; this tool may not reflect recent changes

[ ] I have read and understand these limitations
[ ] I agree to consult a tax professional for my specific situation

[I Acknowledge and Continue]
```

### Audit Trail

Log acknowledgment in existing audit system:

```python
audit_logger.log_event(
    event_type="professional_acknowledgment",
    user_id=user_id,
    session_id=session_id,
    details={
        "acknowledged_at": timestamp,
        "ip_address": ip,
        "checkboxes_accepted": ["limitations", "consult_professional"]
    }
)
```

## Testing Strategy

```python
class TestCircular230Compliance:
    def test_acknowledgment_required_before_chat(self):
        """Chat should require acknowledgment first."""

    def test_acknowledgment_persists_in_session(self):
        """Once acknowledged, user can chat freely."""

    def test_acknowledgment_logged_to_audit(self):
        """Acknowledgment event appears in audit trail."""

    def test_scope_banner_always_visible(self):
        """Scope limitation banner shows in chat UI."""
```

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/web/intelligent_advisor_api.py` | Modify | ~40 |
| `src/web/templates/intelligent_advisor.html` | Modify | ~60 |
| `tests/test_circular_230.py` | Create | ~40 |

**Total: ~140 lines**

## Out of Scope (Future)

- Full engagement letter system
- Conflict-of-interest tracking
- Adverse authority notifications
- Digital signature requirements
