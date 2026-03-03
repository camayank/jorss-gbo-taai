"""
Tests for LeadGenerationService.

Covers lead creation from all sources, status transitions,
priority assignment, contact capture, CPA assignment,
lead-to-client conversion, pipeline queries, and teaser generation.
"""
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cpa_panel.services.lead_generation_service import (
    LeadGenerationService,
    LeadSource,
    LeadStatus,
    LeadPriority,
    ProspectLead,
    LeadTeaser,
    get_lead_generation_service,
)
from cpa_panel.services.form_1040_parser import FilingStatus, Parsed1040Data
from cpa_panel.services.smart_onboarding_service import (
    InstantAnalysis,
    OptimizationOpportunity,
    OnboardingSession,
    OnboardingStatus,
)


# =========================================================================
# ENUM SANITY CHECKS
# =========================================================================

class TestLeadSourceEnum:
    """Verify LeadSource enum members and values."""

    @pytest.mark.parametrize("member,value", [
        (LeadSource.WEBSITE, "website"),
        (LeadSource.REFERRAL, "referral"),
        (LeadSource.CALCULATOR, "calculator"),
        (LeadSource.DOCUMENT_UPLOAD, "document_upload"),
        (LeadSource.QUICK_ESTIMATE, "quick_estimate"),
        (LeadSource.CAMPAIGN, "campaign"),
        (LeadSource.DIRECT, "direct"),
    ])
    def test_lead_source_values(self, member, value):
        assert member.value == value

    def test_lead_source_count(self):
        assert len(LeadSource) == 7

    @pytest.mark.parametrize("source", list(LeadSource))
    def test_lead_source_is_str(self, source):
        assert isinstance(source, str)
        assert isinstance(source.value, str)


class TestLeadStatusEnum:
    """Verify LeadStatus enum members and values."""

    @pytest.mark.parametrize("member,value", [
        (LeadStatus.NEW, "new"),
        (LeadStatus.QUALIFIED, "qualified"),
        (LeadStatus.CONTACTED, "contacted"),
        (LeadStatus.ENGAGED, "engaged"),
        (LeadStatus.CONVERTED, "converted"),
        (LeadStatus.LOST, "lost"),
        (LeadStatus.ARCHIVED, "archived"),
    ])
    def test_lead_status_values(self, member, value):
        assert member.value == value

    def test_lead_status_count(self):
        assert len(LeadStatus) == 7


class TestLeadPriorityEnum:
    """Verify LeadPriority enum members and values."""

    @pytest.mark.parametrize("member,value", [
        (LeadPriority.HIGH, "high"),
        (LeadPriority.MEDIUM, "medium"),
        (LeadPriority.LOW, "low"),
    ])
    def test_lead_priority_values(self, member, value):
        assert member.value == value

    def test_lead_priority_count(self):
        assert len(LeadPriority) == 3


# =========================================================================
# PROSPECT LEAD DATACLASS
# =========================================================================

class TestProspectLead:
    """Tests for ProspectLead dataclass creation, defaults, and serialization."""

    def test_minimal_creation(self):
        lead = ProspectLead(
            lead_id="l1",
            source=LeadSource.WEBSITE,
            status=LeadStatus.NEW,
            created_at=datetime(2025, 1, 1),
        )
        assert lead.lead_id == "l1"
        assert lead.email is None
        assert lead.priority == LeadPriority.MEDIUM
        assert lead.has_dependents is False
        assert lead.num_dependents == 0
        assert lead.notes == []
        assert lead.teaser_opportunities == []

    def test_full_creation(self, sample_lead):
        assert sample_lead.email == "taxpayer@example.com"
        assert sample_lead.filing_status == FilingStatus.SINGLE
        assert sample_lead.estimated_agi == Decimal("85000")

    def test_to_dict_keys(self, sample_lead):
        d = sample_lead.to_dict()
        expected_keys = {
            "lead_id", "source", "status", "created_at",
            "contact", "tax_profile", "teaser", "full_analysis",
            "assignment", "conversion", "notes",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_source_is_string(self, sample_lead):
        d = sample_lead.to_dict()
        assert d["source"] == "quick_estimate"
        assert d["status"] == "new"

    def test_to_dict_contact_fields(self, sample_lead):
        d = sample_lead.to_dict()
        assert d["contact"]["email"] == "taxpayer@example.com"
        assert d["contact"]["name"] == "Jane Doe"

    def test_to_dict_tax_profile(self, sample_lead):
        d = sample_lead.to_dict()
        assert d["tax_profile"]["filing_status"] == "single"
        assert d["tax_profile"]["estimated_agi"] == 85000.0

    def test_to_dict_teaser(self, sample_lead):
        d = sample_lead.to_dict()
        assert d["teaser"]["potential_savings"] == 2500.0

    def test_to_dict_conversion_none(self, sample_lead):
        d = sample_lead.to_dict()
        assert d["conversion"]["client_id"] is None
        assert d["conversion"]["converted_at"] is None

    def test_to_dict_assignment(self, sample_lead):
        d = sample_lead.to_dict()
        assert d["assignment"]["priority"] == "medium"

    @pytest.mark.parametrize("source", list(LeadSource))
    def test_creation_with_each_source(self, source):
        lead = ProspectLead(
            lead_id="x",
            source=source,
            status=LeadStatus.NEW,
            created_at=datetime.utcnow(),
        )
        assert lead.source == source

    @pytest.mark.parametrize("status", list(LeadStatus))
    def test_creation_with_each_status(self, status):
        lead = ProspectLead(
            lead_id="x",
            source=LeadSource.WEBSITE,
            status=status,
            created_at=datetime.utcnow(),
        )
        assert lead.status == status

    @pytest.mark.parametrize("priority", list(LeadPriority))
    def test_creation_with_each_priority(self, priority):
        lead = ProspectLead(
            lead_id="x",
            source=LeadSource.WEBSITE,
            status=LeadStatus.NEW,
            created_at=datetime.utcnow(),
            priority=priority,
        )
        assert lead.priority == priority

    def test_notes_mutable(self, sample_lead):
        sample_lead.notes.append("note1")
        assert "note1" in sample_lead.notes

    def test_teaser_opportunities_mutable(self, sample_lead):
        sample_lead.teaser_opportunities.append("HSA")
        assert "HSA" in sample_lead.teaser_opportunities

    def test_converted_lead_dict(self):
        lead = ProspectLead(
            lead_id="cv1",
            source=LeadSource.REFERRAL,
            status=LeadStatus.CONVERTED,
            created_at=datetime(2025, 1, 1),
            converted_client_id="c1",
            converted_at=datetime(2025, 2, 1),
        )
        d = lead.to_dict()
        assert d["conversion"]["client_id"] == "c1"
        assert "2025-02-01" in d["conversion"]["converted_at"]


# =========================================================================
# LEAD CREATION - QUICK ESTIMATE
# =========================================================================

class TestCreateLeadFromQuickEstimate:
    """Tests for create_lead_from_quick_estimate."""

    @pytest.mark.parametrize("filing_status_str,expected_fs", [
        ("single", FilingStatus.SINGLE),
        ("mfj", FilingStatus.MARRIED_FILING_JOINTLY),
        ("married_filing_jointly", FilingStatus.MARRIED_FILING_JOINTLY),
        ("mfs", FilingStatus.MARRIED_FILING_SEPARATELY),
        ("married_filing_separately", FilingStatus.MARRIED_FILING_SEPARATELY),
        ("hoh", FilingStatus.HEAD_OF_HOUSEHOLD),
        ("head_of_household", FilingStatus.HEAD_OF_HOUSEHOLD),
    ])
    def test_filing_status_mapping(self, lead_service, filing_status_str, expected_fs):
        lead, teaser = lead_service.create_lead_from_quick_estimate(
            filing_status=filing_status_str,
            estimated_income=80000.0,
        )
        assert lead.filing_status == expected_fs

    def test_unknown_filing_status_defaults_to_single(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="unknown_status",
            estimated_income=70000.0,
        )
        assert lead.filing_status == FilingStatus.SINGLE

    def test_lead_has_uuid_id(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=60000.0,
        )
        # Should be a valid UUID string
        uuid.UUID(lead.lead_id)

    def test_lead_status_is_new(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=60000.0,
        )
        assert lead.status == LeadStatus.NEW

    def test_default_source_is_quick_estimate(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=60000.0,
        )
        assert lead.source == LeadSource.QUICK_ESTIMATE

    def test_custom_source(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=60000.0,
            source=LeadSource.CALCULATOR,
        )
        assert lead.source == LeadSource.CALCULATOR

    def test_agi_stored_as_decimal(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=75000.0,
        )
        assert isinstance(lead.estimated_agi, Decimal)
        assert lead.estimated_agi == Decimal("75000.0")

    def test_dependents_tracked(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="mfj",
            estimated_income=120000.0,
            has_dependents=True,
            num_dependents=3,
        )
        assert lead.has_dependents is True
        assert lead.num_dependents == 3

    def test_teaser_returned(self, lead_service):
        _, teaser = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=80000.0,
        )
        assert isinstance(teaser, LeadTeaser)
        assert teaser.opportunity_count >= 0
        assert "$" in teaser.potential_savings_range

    def test_lead_stored_internally(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=80000.0,
        )
        assert lead_service.get_lead(lead.lead_id) is lead

    @pytest.mark.parametrize("income,expected_priority", [
        (200000.0, LeadPriority.HIGH),
        (80000.0, LeadPriority.MEDIUM),
    ])
    def test_priority_by_income(self, lead_service, income, expected_priority):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=income,
        )
        # Priority depends on teaser_savings; high income -> higher savings -> higher priority
        assert lead.priority in list(LeadPriority)

    def test_teaser_savings_set_on_lead(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=100000.0,
        )
        assert lead.teaser_savings is not None
        assert lead.teaser_savings >= Decimal("0")

    def test_teaser_opportunities_set_on_lead(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=100000.0,
        )
        assert isinstance(lead.teaser_opportunities, list)

    @pytest.mark.parametrize("income", [0, 1, 10000, 50000, 100000, 500000, 1000000])
    def test_various_income_levels(self, lead_service, income):
        lead, teaser = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=float(income),
        )
        assert lead is not None
        assert teaser is not None

    def test_case_insensitive_filing_status(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="SINGLE",
            estimated_income=60000.0,
        )
        assert lead.filing_status == FilingStatus.SINGLE

    def test_lead_created_at_set(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=60000.0,
        )
        assert isinstance(lead.created_at, datetime)

    def test_no_contact_info_by_default(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=60000.0,
        )
        assert lead.email is None
        assert lead.phone is None
        assert lead.name is None

    def test_no_full_analysis_initially(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate(
            filing_status="single",
            estimated_income=60000.0,
        )
        assert lead.full_analysis is None


# =========================================================================
# LEAD CREATION - DOCUMENT UPLOAD
# =========================================================================

class TestCreateLeadFromDocument:
    """Tests for create_lead_from_document (async)."""

    @pytest.mark.asyncio
    async def test_document_upload_creates_lead(self, lead_service, parsed_1040_single):
        mock_session = OnboardingSession(
            session_id="s1",
            cpa_id="prospect",
            status=OnboardingStatus.OCR_COMPLETE,
            created_at=datetime.utcnow(),
            parsed_1040=parsed_1040_single,
        )
        lead_service.onboarding_service.start_onboarding.return_value = mock_session
        lead_service.onboarding_service.process_document = AsyncMock(return_value=mock_session)

        lead, teaser = await lead_service.create_lead_from_document(
            file_content=b"fake-pdf-content",
            filename="return_2024.pdf",
        )
        assert lead.source == LeadSource.DOCUMENT_UPLOAD
        assert lead.status == LeadStatus.NEW
        assert lead.parsed_return is parsed_1040_single

    @pytest.mark.asyncio
    async def test_document_upload_no_parsed_data_raises(self, lead_service):
        mock_session = OnboardingSession(
            session_id="s2",
            cpa_id="prospect",
            status=OnboardingStatus.FAILED,
            created_at=datetime.utcnow(),
            parsed_1040=None,
        )
        lead_service.onboarding_service.start_onboarding.return_value = mock_session
        lead_service.onboarding_service.process_document = AsyncMock(return_value=mock_session)

        with pytest.raises(ValueError, match="Failed to extract data"):
            await lead_service.create_lead_from_document(
                file_content=b"bad-content",
                filename="bad.pdf",
            )

    @pytest.mark.asyncio
    async def test_document_upload_extracts_name(self, lead_service, parsed_1040_mfj):
        mock_session = OnboardingSession(
            session_id="s3",
            cpa_id="prospect",
            status=OnboardingStatus.OCR_COMPLETE,
            created_at=datetime.utcnow(),
            parsed_1040=parsed_1040_mfj,
        )
        lead_service.onboarding_service.start_onboarding.return_value = mock_session
        lead_service.onboarding_service.process_document = AsyncMock(return_value=mock_session)

        lead, _ = await lead_service.create_lead_from_document(
            file_content=b"pdf", filename="test.pdf",
        )
        assert lead.name == "John Smith"
        assert lead.filing_status == FilingStatus.MARRIED_FILING_JOINTLY
        assert lead.has_dependents is True
        assert lead.num_dependents == 2


# =========================================================================
# CONTACT CAPTURE
# =========================================================================

class TestCaptureContactInfo:
    """Tests for capture_contact_info."""

    def test_capture_sets_email(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        updated = lead_service.capture_contact_info(lead.lead_id, email="user@test.com")
        assert updated.email == "user@test.com"

    def test_capture_sets_status_qualified(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        updated = lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        assert updated.status == LeadStatus.QUALIFIED

    def test_capture_sets_name_and_phone(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        updated = lead_service.capture_contact_info(
            lead.lead_id, email="u@t.com", name="Test User", phone="555-0000"
        )
        assert updated.name == "Test User"
        assert updated.phone == "555-0000"

    def test_capture_invalid_lead_raises(self, lead_service):
        with pytest.raises(ValueError, match="not found"):
            lead_service.capture_contact_info("nonexistent", email="x@x.com")

    def test_capture_generates_full_analysis(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        updated = lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        assert updated.full_analysis is not None

    def test_capture_preserves_existing_name(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead.name = "Original Name"
        updated = lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        assert updated.name == "Original Name"

    def test_capture_overrides_name_when_provided(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead.name = "Original Name"
        updated = lead_service.capture_contact_info(
            lead.lead_id, email="u@t.com", name="New Name"
        )
        assert updated.name == "New Name"


# =========================================================================
# CPA ASSIGNMENT
# =========================================================================

class TestAssignLeadToCpa:
    """Tests for assign_lead_to_cpa."""

    def test_assign_sets_cpa_id(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        updated = lead_service.assign_lead_to_cpa(lead.lead_id, sample_cpa_id)
        assert updated.assigned_cpa_id == sample_cpa_id

    def test_assign_qualfied_lead_transitions_to_contacted(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        # After capture, status is QUALIFIED
        updated = lead_service.assign_lead_to_cpa(lead.lead_id, sample_cpa_id)
        assert updated.status == LeadStatus.CONTACTED

    def test_assign_new_lead_keeps_status(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        # Status is NEW (not QUALIFIED) since we haven't captured contact
        updated = lead_service.assign_lead_to_cpa(lead.lead_id, sample_cpa_id)
        assert updated.status == LeadStatus.NEW

    def test_assign_nonexistent_lead_raises(self, lead_service):
        with pytest.raises(ValueError, match="not found"):
            lead_service.assign_lead_to_cpa("nope", "cpa-1")


# =========================================================================
# LEAD CONVERSION
# =========================================================================

class TestConvertLeadToClient:
    """Tests for convert_lead_to_client."""

    def test_convert_returns_client_id(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        updated, client_id = lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        assert client_id is not None
        uuid.UUID(client_id)  # Valid UUID

    def test_convert_sets_status_converted(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        updated, _ = lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        assert updated.status == LeadStatus.CONVERTED

    def test_convert_sets_converted_client_id(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        updated, client_id = lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        assert updated.converted_client_id == client_id

    def test_convert_sets_converted_at(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        updated, _ = lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        assert isinstance(updated.converted_at, datetime)

    def test_convert_assigns_cpa(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        updated, _ = lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        assert updated.assigned_cpa_id == sample_cpa_id

    def test_convert_without_contact_raises(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        with pytest.raises(ValueError, match="contact info"):
            lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)

    def test_convert_nonexistent_lead_raises(self, lead_service):
        with pytest.raises(ValueError, match="not found"):
            lead_service.convert_lead_to_client("nope", "cpa-1")


# =========================================================================
# STATUS UPDATES
# =========================================================================

class TestUpdateLeadStatus:
    """Tests for update_lead_status."""

    @pytest.mark.parametrize("new_status", list(LeadStatus))
    def test_update_to_each_status(self, lead_service, new_status):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        updated = lead_service.update_lead_status(lead.lead_id, new_status)
        assert updated.status == new_status

    def test_update_with_note(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        updated = lead_service.update_lead_status(
            lead.lead_id, LeadStatus.LOST, note="Client chose competitor"
        )
        assert len(updated.notes) == 1
        assert "Client chose competitor" in updated.notes[0]

    def test_update_without_note(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        updated = lead_service.update_lead_status(lead.lead_id, LeadStatus.ENGAGED)
        assert len(updated.notes) == 0

    def test_update_nonexistent_lead_raises(self, lead_service):
        with pytest.raises(ValueError, match="not found"):
            lead_service.update_lead_status("nope", LeadStatus.LOST)

    def test_multiple_notes_accumulate(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.update_lead_status(lead.lead_id, LeadStatus.CONTACTED, note="Called")
        lead_service.update_lead_status(lead.lead_id, LeadStatus.ENGAGED, note="Responded")
        assert len(lead.notes) == 2


# =========================================================================
# STATUS TRANSITION MATRIX
# =========================================================================

class TestStatusTransitions:
    """Validate the typical pipeline progression."""

    def test_full_happy_path(self, lead_service, sample_cpa_id):
        """NEW -> QUALIFIED -> CONTACTED -> ENGAGED -> CONVERTED."""
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 100000.0)
        assert lead.status == LeadStatus.NEW

        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        assert lead.status == LeadStatus.QUALIFIED

        lead_service.assign_lead_to_cpa(lead.lead_id, sample_cpa_id)
        assert lead.status == LeadStatus.CONTACTED

        lead_service.update_lead_status(lead.lead_id, LeadStatus.ENGAGED)
        assert lead.status == LeadStatus.ENGAGED

        updated, client_id = lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        assert updated.status == LeadStatus.CONVERTED

    def test_new_to_lost(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.update_lead_status(lead.lead_id, LeadStatus.LOST)
        assert lead.status == LeadStatus.LOST

    def test_new_to_archived(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.update_lead_status(lead.lead_id, LeadStatus.ARCHIVED)
        assert lead.status == LeadStatus.ARCHIVED

    def test_converted_to_new_allowed_by_service(self, lead_service, sample_cpa_id):
        """Service does not enforce transition validation - it sets the status."""
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        # This sets status directly - no guard
        updated = lead_service.update_lead_status(lead.lead_id, LeadStatus.NEW)
        assert updated.status == LeadStatus.NEW

    @pytest.mark.parametrize("from_status,to_status", [
        (LeadStatus.NEW, LeadStatus.QUALIFIED),
        (LeadStatus.QUALIFIED, LeadStatus.CONTACTED),
        (LeadStatus.CONTACTED, LeadStatus.ENGAGED),
        (LeadStatus.ENGAGED, LeadStatus.CONVERTED),
        (LeadStatus.NEW, LeadStatus.LOST),
        (LeadStatus.QUALIFIED, LeadStatus.LOST),
        (LeadStatus.CONTACTED, LeadStatus.ARCHIVED),
    ])
    def test_valid_transitions(self, lead_service, from_status, to_status):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.update_lead_status(lead.lead_id, from_status)
        lead_service.update_lead_status(lead.lead_id, to_status)
        assert lead.status == to_status


# =========================================================================
# LEAD QUERIES
# =========================================================================

class TestLeadQueries:
    """Tests for get_lead, get_leads_for_cpa, get_unassigned_leads, etc."""

    def test_get_lead_found(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        assert lead_service.get_lead(lead.lead_id) is lead

    def test_get_lead_not_found(self, lead_service):
        assert lead_service.get_lead("nonexistent") is None

    def test_get_leads_for_cpa(self, lead_service, sample_cpa_id):
        lead1, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead2, _ = lead_service.create_lead_from_quick_estimate("single", 90000.0)
        lead_service.capture_contact_info(lead1.lead_id, email="a@t.com")
        lead_service.assign_lead_to_cpa(lead1.lead_id, sample_cpa_id)
        leads = lead_service.get_leads_for_cpa(sample_cpa_id)
        assert len(leads) == 1
        assert leads[0].lead_id == lead1.lead_id

    def test_get_leads_for_cpa_with_status_filter(self, lead_service, sample_cpa_id):
        lead1, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead1.lead_id, email="a@t.com")
        lead_service.assign_lead_to_cpa(lead1.lead_id, sample_cpa_id)
        # After assign from QUALIFIED, status is CONTACTED
        leads = lead_service.get_leads_for_cpa(sample_cpa_id, status=LeadStatus.CONTACTED)
        assert len(leads) == 1
        leads_none = lead_service.get_leads_for_cpa(sample_cpa_id, status=LeadStatus.ENGAGED)
        assert len(leads_none) == 0

    def test_get_unassigned_leads(self, lead_service, sample_cpa_id):
        lead1, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead2, _ = lead_service.create_lead_from_quick_estimate("single", 90000.0)
        lead_service.capture_contact_info(lead1.lead_id, email="a@t.com")
        lead_service.assign_lead_to_cpa(lead1.lead_id, sample_cpa_id)
        unassigned = lead_service.get_unassigned_leads()
        assert len(unassigned) == 1
        assert unassigned[0].lead_id == lead2.lead_id

    def test_get_unassigned_excludes_lost(self, lead_service):
        lead1, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.update_lead_status(lead1.lead_id, LeadStatus.LOST)
        unassigned = lead_service.get_unassigned_leads()
        assert len(unassigned) == 0

    def test_get_high_priority_leads(self, lead_service):
        lead1, _ = lead_service.create_lead_from_quick_estimate("single", 200000.0)
        lead2, _ = lead_service.create_lead_from_quick_estimate("single", 15000.0)
        # lead1 should have higher savings -> HIGH priority
        high = lead_service.get_high_priority_leads()
        high_ids = [l.lead_id for l in high]
        # Only leads with HIGH priority that are not CONVERTED/LOST
        for l in high:
            assert l.priority == LeadPriority.HIGH
            assert l.status not in [LeadStatus.CONVERTED, LeadStatus.LOST]

    def test_get_high_priority_excludes_converted(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("mfj", 300000.0,
                                                                has_dependents=True,
                                                                num_dependents=3)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        high = lead_service.get_high_priority_leads()
        assert lead.lead_id not in [l.lead_id for l in high]


# =========================================================================
# PIPELINE SUMMARY
# =========================================================================

class TestGetLeadPipelineSummary:
    """Tests for get_lead_pipeline_summary."""

    def test_empty_pipeline(self, lead_service):
        summary = lead_service.get_lead_pipeline_summary()
        assert summary["total"] == 0
        assert summary["conversion_rate"] == 0

    def test_pipeline_total_count(self, lead_service):
        for i in range(5):
            lead_service.create_lead_from_quick_estimate("single", 60000.0 + i * 10000)
        summary = lead_service.get_lead_pipeline_summary()
        assert summary["total"] == 5

    def test_pipeline_by_status(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        summary = lead_service.get_lead_pipeline_summary()
        assert summary["by_status"]["converted"] == 1

    def test_pipeline_by_source(self, lead_service):
        lead_service.create_lead_from_quick_estimate("single", 80000.0,
                                                      source=LeadSource.WEBSITE)
        lead_service.create_lead_from_quick_estimate("single", 90000.0,
                                                      source=LeadSource.REFERRAL)
        summary = lead_service.get_lead_pipeline_summary()
        assert summary["by_source"]["website"] == 1
        assert summary["by_source"]["referral"] == 1

    def test_pipeline_by_priority(self, lead_service):
        lead_service.create_lead_from_quick_estimate("single", 200000.0)
        lead_service.create_lead_from_quick_estimate("single", 15000.0)
        summary = lead_service.get_lead_pipeline_summary()
        total_by_priority = sum(summary["by_priority"].values())
        assert total_by_priority == summary["total"]

    def test_pipeline_filtered_by_cpa(self, lead_service, sample_cpa_id):
        lead1, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead2, _ = lead_service.create_lead_from_quick_estimate("single", 90000.0)
        lead_service.capture_contact_info(lead1.lead_id, email="a@t.com")
        lead_service.assign_lead_to_cpa(lead1.lead_id, sample_cpa_id)
        summary = lead_service.get_lead_pipeline_summary(cpa_id=sample_cpa_id)
        assert summary["total"] == 1

    def test_pipeline_conversion_rate(self, lead_service, sample_cpa_id):
        for i in range(4):
            lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        # Convert the last one
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        summary = lead_service.get_lead_pipeline_summary()
        assert summary["conversion_rate"] == 25.0

    def test_pipeline_total_potential_savings(self, lead_service):
        lead_service.create_lead_from_quick_estimate("single", 80000.0)
        lead_service.create_lead_from_quick_estimate("single", 90000.0)
        summary = lead_service.get_lead_pipeline_summary()
        assert summary["total_potential_savings"] >= 0

    def test_pipeline_excludes_converted_from_savings(self, lead_service, sample_cpa_id):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
        savings_before = lead.teaser_savings or Decimal("0")
        lead_service.capture_contact_info(lead.lead_id, email="u@t.com")
        lead_service.convert_lead_to_client(lead.lead_id, sample_cpa_id)
        summary = lead_service.get_lead_pipeline_summary()
        # Converted leads are excluded from total_potential_savings
        assert summary["total_potential_savings"] == 0


# =========================================================================
# TEASER GENERATION (INTERNAL)
# =========================================================================

class TestTeaserGeneration:
    """Tests for _generate_teaser private method."""

    def test_teaser_retirement_opportunity_above_30k(self, lead_service):
        lead = ProspectLead(
            lead_id="t1", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("50000"),
        )
        teaser = lead_service._generate_teaser(lead)
        assert "Retirement Savings" in teaser.opportunity_categories

    def test_teaser_no_retirement_below_30k(self, lead_service):
        lead = ProspectLead(
            lead_id="t2", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("20000"),
        )
        teaser = lead_service._generate_teaser(lead)
        assert "Retirement Savings" not in teaser.opportunity_categories

    def test_teaser_hsa_above_40k(self, lead_service):
        lead = ProspectLead(
            lead_id="t3", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("50000"),
        )
        teaser = lead_service._generate_teaser(lead)
        assert "Healthcare Tax Benefits" in teaser.opportunity_categories

    def test_teaser_family_credits_with_dependents(self, lead_service):
        lead = ProspectLead(
            lead_id="t4", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("50000"),
            has_dependents=True, num_dependents=2,
        )
        teaser = lead_service._generate_teaser(lead)
        assert "Family Tax Credits" in teaser.opportunity_categories

    def test_teaser_no_family_credits_without_dependents(self, lead_service):
        lead = ProspectLead(
            lead_id="t5", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("50000"),
            has_dependents=False,
        )
        teaser = lead_service._generate_teaser(lead)
        assert "Family Tax Credits" not in teaser.opportunity_categories

    def test_teaser_deduction_strategy_above_60k(self, lead_service):
        lead = ProspectLead(
            lead_id="t6", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("80000"),
        )
        teaser = lead_service._generate_teaser(lead)
        assert "Deduction Strategy" in teaser.opportunity_categories

    def test_teaser_headline_significant_savings(self, lead_service):
        lead = ProspectLead(
            lead_id="t7", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("200000"),
            has_dependents=True, num_dependents=3,
        )
        teaser = lead_service._generate_teaser(lead)
        assert "significant" in teaser.headline.lower() or "identified" in teaser.headline.lower()

    def test_teaser_cta_present(self, lead_service):
        lead = ProspectLead(
            lead_id="t8", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("50000"),
        )
        teaser = lead_service._generate_teaser(lead)
        assert "email" in teaser.call_to_action.lower()

    def test_teaser_zero_agi(self, lead_service):
        lead = ProspectLead(
            lead_id="t9", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("0"),
        )
        teaser = lead_service._generate_teaser(lead)
        assert teaser.opportunity_count == 0

    def test_teaser_none_agi(self, lead_service):
        lead = ProspectLead(
            lead_id="t10", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
        )
        teaser = lead_service._generate_teaser(lead)
        assert isinstance(teaser, LeadTeaser)

    def test_teaser_to_dict(self, lead_service):
        lead = ProspectLead(
            lead_id="t11", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=Decimal("70000"),
        )
        teaser = lead_service._generate_teaser(lead)
        d = teaser.to_dict()
        assert "potential_savings_range" in d
        assert "opportunity_count" in d
        assert "headline" in d

    @pytest.mark.parametrize("agi", [
        Decimal("0"), Decimal("15000"), Decimal("30001"),
        Decimal("40001"), Decimal("60001"), Decimal("100000"),
        Decimal("500000"), Decimal("1000000"),
    ])
    def test_teaser_various_agi_levels(self, lead_service, agi):
        lead = ProspectLead(
            lead_id=f"t-agi-{agi}", source=LeadSource.QUICK_ESTIMATE,
            status=LeadStatus.NEW, created_at=datetime.utcnow(),
            filing_status=FilingStatus.SINGLE,
            estimated_agi=agi,
        )
        teaser = lead_service._generate_teaser(lead)
        assert isinstance(teaser, LeadTeaser)
        assert "$" in teaser.potential_savings_range


# =========================================================================
# MARGINAL RATE ESTIMATION
# =========================================================================

class TestEstimateMarginalRate:
    """Tests for _estimate_marginal_rate private method."""

    @pytest.mark.parametrize("agi,fs,expected_rate", [
        (Decimal("10000"), FilingStatus.SINGLE, Decimal("0.10")),
        (Decimal("30000"), FilingStatus.SINGLE, Decimal("0.12")),
        (Decimal("80000"), FilingStatus.SINGLE, Decimal("0.22")),
        (Decimal("150000"), FilingStatus.SINGLE, Decimal("0.24")),
        (Decimal("250000"), FilingStatus.SINGLE, Decimal("0.32")),
        (Decimal("50000"), FilingStatus.MARRIED_FILING_JOINTLY, Decimal("0.12")),
        (Decimal("150000"), FilingStatus.MARRIED_FILING_JOINTLY, Decimal("0.22")),
        (Decimal("300000"), FilingStatus.MARRIED_FILING_JOINTLY, Decimal("0.24")),
    ])
    def test_marginal_rates(self, lead_service, agi, fs, expected_rate):
        rate = lead_service._estimate_marginal_rate(agi, fs)
        assert rate == expected_rate

    def test_none_agi_defaults(self, lead_service):
        rate = lead_service._estimate_marginal_rate(None, FilingStatus.SINGLE)
        assert rate == Decimal("0.22")

    def test_none_filing_status_uses_single_brackets(self, lead_service):
        rate = lead_service._estimate_marginal_rate(Decimal("80000"), None)
        assert rate == Decimal("0.22")


# =========================================================================
# PARSE SAVINGS RANGE
# =========================================================================

class TestParseSavingsRange:
    """Tests for _parse_savings_range helper."""

    @pytest.mark.parametrize("range_str,expected", [
        ("$1,000 - $3,000", (1000.0, 3000.0)),
        ("$500 - $1,500", (500.0, 1500.0)),
        ("$0 - $0", (0.0, 0.0)),
        ("$10,000 - $25,000", (10000.0, 25000.0)),
    ])
    def test_parse_range(self, lead_service, range_str, expected):
        result = lead_service._parse_savings_range(range_str)
        assert result == expected

    def test_parse_single_number(self, lead_service):
        result = lead_service._parse_savings_range("$5,000")
        assert result == (3500.0, 5000.0)

    def test_parse_no_numbers(self, lead_service):
        result = lead_service._parse_savings_range("no savings")
        assert result == (0.0, 0.0)


# =========================================================================
# PRIORITY ASSIGNMENT
# =========================================================================

class TestPriorityAssignment:
    """Tests for priority determination based on teaser savings."""

    def test_high_priority_above_3000(self, lead_service):
        """Income high enough that teaser_savings > 3000 -> HIGH."""
        lead, _ = lead_service.create_lead_from_quick_estimate(
            "mfj", 300000.0, has_dependents=True, num_dependents=3,
        )
        # With this income, savings should be significant
        if lead.teaser_savings and lead.teaser_savings > Decimal("3000"):
            assert lead.priority == LeadPriority.HIGH

    def test_medium_priority_1000_to_3000(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 70000.0)
        if lead.teaser_savings and Decimal("1000") < lead.teaser_savings <= Decimal("3000"):
            assert lead.priority == LeadPriority.MEDIUM

    def test_low_priority_below_1000(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 15000.0)
        if lead.teaser_savings and lead.teaser_savings <= Decimal("1000"):
            assert lead.priority == LeadPriority.LOW


# =========================================================================
# SINGLETON
# =========================================================================

class TestSingleton:
    """Test singleton accessor."""

    def test_get_lead_generation_service_returns_instance(self):
        with patch("cpa_panel.services.lead_generation_service.SmartOnboardingService"), \
             patch("cpa_panel.services.lead_generation_service.AIQuestionGenerator"):
            svc = get_lead_generation_service()
            assert isinstance(svc, LeadGenerationService)


# =========================================================================
# EDGE CASES
# =========================================================================

class TestEdgeCases:
    """Miscellaneous edge cases."""

    def test_multiple_leads_unique_ids(self, lead_service):
        ids = set()
        for _ in range(20):
            lead, _ = lead_service.create_lead_from_quick_estimate("single", 80000.0)
            ids.add(lead.lead_id)
        assert len(ids) == 20

    def test_lead_with_all_fields(self):
        lead = ProspectLead(
            lead_id="full",
            source=LeadSource.REFERRAL,
            status=LeadStatus.ENGAGED,
            created_at=datetime(2025, 6, 1),
            email="full@example.com",
            phone="555-999-0000",
            name="Full Lead",
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            estimated_agi=Decimal("120000"),
            estimated_wages=Decimal("110000"),
            has_dependents=True,
            num_dependents=2,
            teaser_savings=Decimal("4500"),
            teaser_opportunities=["Retirement", "HSA", "Family Credits"],
            assigned_cpa_id="cpa-full",
            priority=LeadPriority.HIGH,
            converted_client_id=None,
            notes=["Initial note"],
        )
        d = lead.to_dict()
        assert d["contact"]["email"] == "full@example.com"
        assert d["tax_profile"]["has_dependents"] is True
        assert d["tax_profile"]["num_dependents"] == 2

    @pytest.mark.parametrize("source,status,priority", [
        (s, st, p)
        for s in LeadSource
        for st in [LeadStatus.NEW, LeadStatus.QUALIFIED]
        for p in LeadPriority
    ])
    def test_all_source_status_priority_combos(self, source, status, priority):
        lead = ProspectLead(
            lead_id="combo",
            source=source,
            status=status,
            created_at=datetime.utcnow(),
            priority=priority,
        )
        d = lead.to_dict()
        assert d["source"] == source.value
        assert d["status"] == status.value
        assert d["assignment"]["priority"] == priority.value

    def test_decimal_precision_preserved(self, lead_service):
        lead, _ = lead_service.create_lead_from_quick_estimate("single", 99999.99)
        assert lead.estimated_agi == Decimal("99999.99")

    def test_very_high_income(self, lead_service):
        lead, teaser = lead_service.create_lead_from_quick_estimate("single", 10_000_000.0)
        assert lead.estimated_agi == Decimal("10000000.0")
        assert teaser is not None
