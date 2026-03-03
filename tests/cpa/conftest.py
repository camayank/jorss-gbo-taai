"""
Shared fixtures for CPA panel service tests.

Provides sample data, factory functions, and mock dependencies
for lead generation, onboarding, pipeline, scenario, and activity services.
"""
import os
import sys
import uuid
import tempfile
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
)
from cpa_panel.services.activity_service import (
    ActivityService,
    ActivityType,
    ActivityActor,
    Activity,
)
from cpa_panel.services.form_1040_parser import (
    FilingStatus,
    Parsed1040Data,
    DependentInfo,
)
from cpa_panel.services.smart_onboarding_service import (
    SmartOnboardingService,
    OnboardingSession,
    OnboardingStatus,
    OptimizationOpportunity,
    InstantAnalysis,
)


# =========================================================================
# LEAD DATA FIXTURES
# =========================================================================

@pytest.fixture
def sample_lead_id():
    """Return a stable lead ID for tests."""
    return "lead-test-00000001"


@pytest.fixture
def sample_cpa_id():
    """Return a stable CPA ID for tests."""
    return "cpa-test-00000001"


@pytest.fixture
def sample_client_id():
    """Return a stable client ID for tests."""
    return "client-test-00000001"


@pytest.fixture
def now():
    """Return a fixed datetime for deterministic tests."""
    return datetime(2025, 3, 15, 10, 0, 0)


@pytest.fixture
def sample_lead_data():
    """Minimal data dict to create a ProspectLead."""
    return {
        "lead_id": "lead-test-00000001",
        "source": LeadSource.QUICK_ESTIMATE,
        "status": LeadStatus.NEW,
        "created_at": datetime(2025, 3, 15, 10, 0, 0),
        "email": "taxpayer@example.com",
        "phone": "555-123-4567",
        "name": "Jane Doe",
        "filing_status": FilingStatus.SINGLE,
        "estimated_agi": Decimal("85000"),
        "estimated_wages": Decimal("85000"),
        "has_dependents": False,
        "num_dependents": 0,
        "teaser_savings": Decimal("2500"),
        "priority": LeadPriority.MEDIUM,
    }


@pytest.fixture
def sample_lead(sample_lead_data):
    """Create a ProspectLead from sample data."""
    return ProspectLead(**sample_lead_data)


@pytest.fixture
def sample_lead_high_income():
    """A high-income lead that should be HIGH priority."""
    return ProspectLead(
        lead_id="lead-high-income",
        source=LeadSource.DOCUMENT_UPLOAD,
        status=LeadStatus.QUALIFIED,
        created_at=datetime(2025, 3, 15, 10, 0, 0),
        email="highearner@example.com",
        name="John Rich",
        filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        estimated_agi=Decimal("350000"),
        estimated_wages=Decimal("350000"),
        has_dependents=True,
        num_dependents=3,
        teaser_savings=Decimal("8500"),
        priority=LeadPriority.HIGH,
    )


@pytest.fixture
def sample_lead_low_income():
    """A low-income lead that should be LOW priority."""
    return ProspectLead(
        lead_id="lead-low-income",
        source=LeadSource.WEBSITE,
        status=LeadStatus.NEW,
        created_at=datetime(2025, 3, 15, 10, 0, 0),
        filing_status=FilingStatus.SINGLE,
        estimated_agi=Decimal("20000"),
        estimated_wages=Decimal("20000"),
        has_dependents=False,
        num_dependents=0,
        teaser_savings=Decimal("200"),
        priority=LeadPriority.LOW,
    )


def make_lead(
    lead_id=None,
    source=LeadSource.QUICK_ESTIMATE,
    status=LeadStatus.NEW,
    email=None,
    name=None,
    filing_status=FilingStatus.SINGLE,
    agi=Decimal("75000"),
    savings=Decimal("2000"),
    priority=LeadPriority.MEDIUM,
    cpa_id=None,
    has_dependents=False,
    num_dependents=0,
):
    """Factory function to create ProspectLead with defaults."""
    return ProspectLead(
        lead_id=lead_id or f"lead-{uuid.uuid4().hex[:8]}",
        source=source,
        status=status,
        created_at=datetime.utcnow(),
        email=email,
        name=name,
        filing_status=filing_status,
        estimated_agi=agi,
        estimated_wages=agi,
        has_dependents=has_dependents,
        num_dependents=num_dependents,
        teaser_savings=savings,
        priority=priority,
        assigned_cpa_id=cpa_id,
    )


@pytest.fixture
def lead_factory():
    """Expose the make_lead factory as a fixture."""
    return make_lead


# =========================================================================
# SERVICE FIXTURES
# =========================================================================

@pytest.fixture
def mock_onboarding_service():
    """Mocked SmartOnboardingService that skips OCR/AI calls."""
    with patch(
        "cpa_panel.services.lead_generation_service.SmartOnboardingService"
    ) as MockCls:
        mock_svc = MagicMock(spec=SmartOnboardingService)
        MockCls.return_value = mock_svc
        yield mock_svc


@pytest.fixture
def mock_question_generator():
    """Mocked AIQuestionGenerator."""
    with patch(
        "cpa_panel.services.lead_generation_service.AIQuestionGenerator"
    ) as MockCls:
        mock_gen = MagicMock()
        MockCls.return_value = mock_gen
        yield mock_gen


@pytest.fixture
def lead_service(mock_onboarding_service, mock_question_generator):
    """LeadGenerationService with mocked dependencies."""
    svc = LeadGenerationService()
    return svc


# =========================================================================
# 1040 PARSED DATA FIXTURES
# =========================================================================

@pytest.fixture
def parsed_1040_single():
    """Parsed 1040 for a single filer, moderate income."""
    return Parsed1040Data(
        tax_year=2024,
        taxpayer_name="Jane Doe",
        filing_status=FilingStatus.SINGLE,
        total_dependents=0,
        wages_salaries_tips=Decimal("85000"),
        total_income=Decimal("87000"),
        adjustments_to_income=Decimal("2000"),
        adjusted_gross_income=Decimal("85000"),
        standard_deduction=Decimal("14600"),
        total_deductions=Decimal("14600"),
        taxable_income=Decimal("70400"),
        tax=Decimal("11268"),
        total_tax=Decimal("11268"),
        federal_withholding=Decimal("12000"),
        refund_amount=Decimal("732"),
        extraction_confidence=92.0,
        fields_extracted=18,
    )


@pytest.fixture
def parsed_1040_mfj():
    """Parsed 1040 for married filing jointly, two dependents."""
    return Parsed1040Data(
        tax_year=2024,
        taxpayer_name="John Smith",
        spouse_name="Mary Smith",
        filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        total_dependents=2,
        dependents=[
            DependentInfo(name="Alice Smith", relationship="daughter", child_tax_credit=True),
            DependentInfo(name="Bob Smith", relationship="son", child_tax_credit=True),
        ],
        wages_salaries_tips=Decimal("150000"),
        total_income=Decimal("155000"),
        adjusted_gross_income=Decimal("150000"),
        standard_deduction=Decimal("29200"),
        total_deductions=Decimal("29200"),
        taxable_income=Decimal("120800"),
        tax=Decimal("18560"),
        child_tax_credit=Decimal("4000"),
        total_tax=Decimal("14560"),
        federal_withholding=Decimal("16000"),
        refund_amount=Decimal("1440"),
        extraction_confidence=88.5,
        fields_extracted=22,
    )


# =========================================================================
# ANALYSIS FIXTURES
# =========================================================================

@pytest.fixture
def sample_opportunity():
    """Single OptimizationOpportunity."""
    return OptimizationOpportunity(
        id="opp_401k",
        title="Maximize 401(k) Contributions",
        category="retirement",
        potential_savings=Decimal("3500"),
        confidence="high",
        description="Increase 401(k) contributions to maximum $23,500",
        action_required="Contact HR to increase contribution rate",
        priority=1,
    )


@pytest.fixture
def sample_analysis(sample_opportunity):
    """InstantAnalysis with one opportunity."""
    return InstantAnalysis(
        total_potential_savings=Decimal("3500"),
        opportunities=[sample_opportunity],
        tax_summary={
            "tax_year": 2024,
            "filing_status": "single",
            "adjusted_gross_income": 85000.0,
            "total_income": 87000.0,
            "total_tax": 11268.0,
            "effective_rate": 13.26,
            "refund_or_owed": 732.0,
        },
        recommendations_count=1,
        analysis_confidence="high",
    )


# =========================================================================
# TEASER FIXTURE
# =========================================================================

@pytest.fixture
def sample_teaser():
    """A LeadTeaser for tests that skip teaser generation."""
    return LeadTeaser(
        potential_savings_range="$1,500 - $3,500",
        opportunity_count=3,
        opportunity_categories=["Retirement Savings", "Healthcare Tax Benefits", "Deduction Strategy"],
        headline="We identified potential ways to reduce your taxes.",
        call_to_action="Enter your email to see your personalized tax savings report.",
    )


# =========================================================================
# ACTIVITY DATA FIXTURES
# =========================================================================

@pytest.fixture
def activity_db_path(tmp_path):
    """Temporary SQLite DB path for activity service tests."""
    return str(tmp_path / "test_activities.db")


@pytest.fixture
def activity_service(activity_db_path):
    """ActivityService backed by a temporary database."""
    return ActivityService(db_path=activity_db_path)


@pytest.fixture
def sample_activity_data():
    """Dict of kwargs for log_activity."""
    return {
        "lead_id": "lead-test-00000001",
        "activity_type": ActivityType.LEAD_CREATED,
        "actor": ActivityActor.SYSTEM,
        "description": "Lead created from quick estimate",
        "metadata": {"session_id": "sess-001"},
    }


@pytest.fixture
def populated_activity_service(activity_service, sample_lead_id, sample_cpa_id):
    """ActivityService pre-loaded with several activities for timeline tests."""
    svc = activity_service
    lead = sample_lead_id
    cpa = sample_cpa_id

    svc.log_activity(lead, ActivityType.LEAD_CREATED, ActivityActor.SYSTEM)
    svc.log_activity(lead, ActivityType.LEAD_CAPTURED, ActivityActor.SYSTEM,
                     metadata={"email": "test@example.com"})
    svc.log_activity(lead, ActivityType.STATE_CHANGE, ActivityActor.SYSTEM,
                     metadata={"old_state": "new", "new_state": "qualified"})
    svc.log_activity(lead, ActivityType.CPA_VIEWED, ActivityActor.CPA,
                     actor_id=cpa, actor_name="CPA Jones")
    svc.log_activity(lead, ActivityType.CPA_NOTE_ADDED, ActivityActor.CPA,
                     actor_id=cpa, actor_name="CPA Jones",
                     metadata={"note": "Promising lead"})
    svc.log_activity(lead, ActivityType.EMAIL_SENT, ActivityActor.SYSTEM,
                     metadata={"subject": "Welcome", "recipient": "test@example.com"})
    svc.log_activity(lead, ActivityType.REPORT_GENERATED, ActivityActor.SYSTEM)
    return svc
