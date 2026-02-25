# Audit Trail Improvements (MVP) Design Document

**Date:** 2026-02-25
**Status:** Approved
**Approach:** AI Rationale Logging (MVP)

## Overview

Enhance audit trail to capture AI decision rationale, enabling defense of calculations in IRS audits and proving what advice was given with what confidence.

## Problem

The SWOT analysis identified "Audit Trail Missing AI Decision Rationale" as a Risk 7/10 issue:
- Current: Tracks events (login, return create, document upload)
- Missing: Why AI made decisions, confidence levels, model version, data provenance

Impact: Can't defend calculations in IRS audit; can't prove user provided incorrect data.

## MVP Design

### Enhanced Audit Event Structure

**File: `src/audit/audit_logger.py`**

Add new fields to audit events:

```python
class AIResponseAuditEvent(BaseModel):
    """Audit event for AI advisory responses."""
    event_type: str = "ai_response"
    timestamp: datetime
    session_id: str
    user_id: Optional[str]

    # New fields for AI rationale
    model_version: str  # e.g., "gpt-4-turbo-2024-04-09"
    prompt_hash: str  # SHA256 of system prompt for reproducibility
    response_type: str  # greeting, question, calculation, strategy

    # Confidence tracking
    profile_completeness: float  # 0.0-1.0 at time of response
    response_confidence: str  # high, medium, low
    confidence_reason: Optional[str]

    # Input tracking
    user_message: str
    extracted_fields: dict  # What was extracted from user input
    calculation_inputs: Optional[dict]  # Inputs used for any calculations

    # Output tracking
    response_summary: str  # First 200 chars of response
    citations_included: list[str]  # Tax law citations added
    warnings_triggered: list[str]  # Any warnings shown
```

### Logging Integration

**File: `src/web/intelligent_advisor_api.py`**

Add audit logging to chat endpoint:

```python
def log_ai_response(
    session_id: str,
    user_message: str,
    response: ChatResponse,
    profile: dict,
    model_info: dict
):
    """Log AI response with full rationale for audit trail."""
    audit_event = AIResponseAuditEvent(
        timestamp=datetime.utcnow(),
        session_id=session_id,
        model_version=model_info.get("model", "unknown"),
        prompt_hash=get_prompt_hash(),
        response_type=response.response_type,
        profile_completeness=response.profile_completeness,
        response_confidence=response.response_confidence,
        confidence_reason=response.confidence_reason,
        user_message=user_message[:500],  # Truncate for storage
        extracted_fields=response.extracted_data or {},
        calculation_inputs=response.tax_calculation or {},
        response_summary=response.response[:200],
        citations_included=response.citations or [],
        warnings_triggered=response.warnings or []
    )
    audit_logger.log_ai_event(audit_event)
```

### Calculation Audit Trail

For tax calculations, log the specific inputs used:

```python
calculation_inputs = {
    "tax_year": 2025,
    "filing_status": "married_filing_jointly",
    "total_income": 150000,
    "adjustments": {"ira_contribution": 6500},
    "deduction_type": "standard",
    "credits_claimed": ["child_tax_credit"],
    "dependents": 2
}
```

### Query Interface

Add method to retrieve audit history:

```python
def get_session_audit_trail(session_id: str) -> list[AIResponseAuditEvent]:
    """Get complete audit trail for a session."""
    return audit_logger.get_events_by_session(session_id)
```

## Testing Strategy

```python
class TestAuditTrailImprovements:
    def test_ai_response_logged_with_model_version(self):
        """AI responses include model version in audit."""

    def test_calculation_inputs_captured(self):
        """Tax calculations log their input values."""

    def test_confidence_levels_logged(self):
        """Response confidence is captured in audit trail."""

    def test_audit_trail_retrievable_by_session(self):
        """Can query full audit history for a session."""

    def test_prompt_hash_consistent(self):
        """Same prompt produces same hash for reproducibility."""
```

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `src/audit/audit_logger.py` | Modify | ~50 |
| `src/web/intelligent_advisor_api.py` | Modify | ~30 |
| `tests/test_audit_trail.py` | Create | ~60 |

**Total: ~140 lines**

## Out of Scope (Future)

- Complete decision tree logging
- ML model weight versioning
- Field-level data provenance (which document each field came from)
- Audit report generation
- Long-term audit storage (beyond session)
