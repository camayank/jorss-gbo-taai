# IRS e-File (MeF) Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement IRS Modernized e-File (MeF) XML pipeline to enable direct filing of Form 1040 returns to the IRS with full compliance.

**Architecture:**
The MeF pipeline consists of five loosely-coupled layers: (1) XML generation from TaxReturnRecord to IRS-compliant Form 1040 XML per Publication 4164, (2) XSD validation against IRS schema bundles, (3) IRS API client (SOAP-based per MeF spec) with EFIN credential management, (4) async submission polling with ACK/REJ tracking, (5) error parsing and user-facing feedback. Each layer is independently testable and can be deployed/versioned separately.

**Tech Stack:**
- XML: `lxml` for generation and validation (XSD parsing)
- IRS API: SOAP client via `zeep` library (MeF spec requires SOAP/HTTP over HTTPS)
- Async: `asyncio` + existing `AsyncTaxReturnService` pattern
- Database: New `IrsSubmission` and `IrsSubmissionAck` models + 7-year retention policy
- Testing: pytest with fixtures for mock IRS responses

---

## Phase 1: Database Models & Storage

### Task 1: Create IRS Submission Model

**Files:**
- Modify: `src/database/models.py` (add `IrsSubmission` table)
- Create: `src/database/repositories/irs_submission_repository.py`
- Test: `tests/integration/test_irs_submission_models.py`

**Step 1: Write the failing test**

```python
# tests/integration/test_irs_submission_models.py
import pytest
from datetime import datetime, timezone
from uuid import uuid4
from decimal import Decimal

from database.models import IrsSubmission, IrsSubmissionStatus
from database import Base, engine, Session


def test_irs_submission_model_creation():
    """Test IrsSubmission model can be created and stored."""
    with Session(engine) as session:
        submission = IrsSubmission(
            submission_id=uuid4(),
            return_id=uuid4(),
            firm_id=uuid4(),
            form_type="1040",
            tax_year=2025,
            submission_batch_id="MCC20260405000001",
            xml_content="<form1040>...</form1040>",
            submission_status=IrsSubmissionStatus.DRAFT,
            submitted_at=None,
            test_mode=True
        )
        session.add(submission)
        session.commit()

        fetched = session.query(IrsSubmission).filter_by(
            submission_id=submission.submission_id
        ).first()
        assert fetched is not None
        assert fetched.form_type == "1040"
        assert fetched.submission_status == IrsSubmissionStatus.DRAFT
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
pytest tests/integration/test_irs_submission_models.py::test_irs_submission_model_creation -v
# Expected: FAIL — IrsSubmission not defined
```

**Step 3: Write model and enum to src/database/models.py**

Append these to the models file:

```python
class IrsSubmissionStatus(str, PyEnum):
    """IRS submission status FSM."""
    DRAFT = "draft"
    VALIDATION_IN_PROGRESS = "validation_in_progress"
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    SUBMITTED = "submitted"
    AWAITING_ACK = "awaiting_ack"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class IrsSubmission(Base):
    """IRS MeF submission record."""
    __tablename__ = "irs_submissions"

    submission_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    return_id = Column(UUID(as_uuid=True), ForeignKey("tax_returns.return_id", ondelete="CASCADE"), nullable=False, index=True)
    firm_id = Column(UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="CASCADE"), nullable=False, index=True)

    form_type = Column(String(20), nullable=False, default="1040")
    tax_year = Column(Integer, nullable=False, index=True)
    submission_batch_id = Column(String(50), nullable=False, unique=True, index=True)

    xml_content = Column(Text, nullable=False)
    submission_status = Column(Enum(IrsSubmissionStatus), nullable=False, default=IrsSubmissionStatus.DRAFT, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    ack_received_at = Column(DateTime, nullable=True)

    test_mode = Column(Boolean, default=False, index=True)

    __table_args__ = (
        Index('ix_submission_return_year', 'return_id', 'tax_year'),
        Index('ix_submission_firm_status', 'firm_id', 'submission_status'),
    )


class IrsSubmissionAck(Base):
    """IRS Acknowledgment response."""
    __tablename__ = "irs_submission_acks"

    ack_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("irs_submissions.submission_id", ondelete="CASCADE"), nullable=False, index=True, unique=True)

    ack_xml = Column(Text, nullable=False)
    ack_type = Column(String(10), nullable=False)
    transmission_id = Column(String(50), nullable=True)
    acknowledgment_code = Column(String(10), nullable=True)

    error_count = Column(Integer, default=0)
    error_details = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/integration/test_irs_submission_models.py::test_irs_submission_model_creation -v
# Expected: PASS
```

**Step 5: Commit**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
git add src/database/models.py tests/integration/test_irs_submission_models.py
git commit -m "feat: add IrsSubmission and IrsSubmissionAck models for MeF pipeline

- IrsSubmission: tracks Form 1040 submission lifecycle
- IrsSubmissionAck: stores IRS ACK/REJ response
- 7-year retention for compliance
- Test mode flag for IRS Assurance Testing System (ATS)

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Implementation Checklist

- [ ] Task 1: IRS Submission models
- [ ] Task 2: IRS Submission repository  
- [ ] Task 3: MeF XML generator
- [ ] Task 4: XSD validator
- [ ] Task 5: IRS MeF SOAP client
- [ ] Task 6: MeF submission service
- [ ] Task 7: ACK/REJ polling service
- [ ] Task 8: API endpoints
- [ ] Task 9: Integration tests
- [ ] Task 10: Monitoring & audit

---

## Compliance Notes

- All submission/ACK XML stored for 7 years (IrsSubmission/IrsSubmissionAck models)
- Test mode uses IRS Assurance Testing System (ATS)
- Production requires EFIN and PIN registration
- SOAP envelope per IRS Publication 4164
- Business rule validation (income consistency, etc.)

## Dependencies

Add to `requirements.txt`:
```
lxml>=4.9.2
zeep>=4.2.1
```
