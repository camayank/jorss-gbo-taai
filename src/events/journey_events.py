"""
Journey Event Types

Typed dataclasses for every transition in the client tax journey.
Emitted by subsystems, consumed by the ClientJourneyOrchestrator.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class AdvisorProfileComplete:
    """Advisor has collected enough profile data to proceed."""
    session_id: str
    tenant_id: str
    user_id: str
    profile_completeness: float
    extracted_forms: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AdvisorMessageSent:
    """User sent a message in the advisor chat (for input guard)."""
    session_id: str
    tenant_id: str
    user_id: str
    message_text: str


@dataclass(frozen=True)
class DocumentProcessed:
    """A document was uploaded and OCR/extraction completed."""
    document_id: str
    tenant_id: str
    user_id: str
    document_type: str
    fields_extracted: int


@dataclass(frozen=True)
class ReturnDraftSaved:
    """A tax return draft was saved or updated."""
    return_id: str
    tenant_id: str
    user_id: str
    session_id: str
    completeness: float = 0.0


@dataclass(frozen=True)
class ReturnSubmittedForReview:
    """Client submitted their return for CPA review."""
    session_id: str
    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class ScenarioCreated:
    """A what-if tax scenario was created."""
    scenario_id: str
    tenant_id: str
    user_id: str
    return_id: str
    name: str
    savings_amount: float = 0.0


@dataclass(frozen=True)
class ReviewCompleted:
    """CPA completed review (approved or rejected)."""
    session_id: str
    tenant_id: str
    user_id: str
    cpa_id: str
    status: str
    notes: Optional[str] = None


@dataclass(frozen=True)
class ReportGenerated:
    """Final tax report/advisory report was generated."""
    report_id: str
    tenant_id: str
    user_id: str
    session_id: str
    download_url: Optional[str] = None


@dataclass(frozen=True)
class LeadStateChanged:
    """Lead state changed in the CPA pipeline."""
    lead_id: str
    tenant_id: str
    user_id: str
    from_state: str
    to_state: str
    trigger: str  # "manual", "score_threshold", "time_based"
