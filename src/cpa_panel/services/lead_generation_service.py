"""
Lead Generation Service - Generates and manages prospect leads.

This service supports the lead generation flow:
1. Prospect uploads 1040 (or answers basic questions)
2. System shows teaser of potential savings
3. Prospect provides contact info to see full analysis
4. Lead is created and assigned to CPA
5. CPA can convert lead to client
"""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum

from .form_1040_parser import Parsed1040Data, FilingStatus
from .ai_question_generator import AIQuestionGenerator, QuestionSet
from .smart_onboarding_service import (
    SmartOnboardingService,
    OptimizationOpportunity,
    InstantAnalysis,
)

logger = logging.getLogger(__name__)


class LeadSource(str, Enum):
    """Source of the lead."""
    WEBSITE = "website"  # Landed on website
    REFERRAL = "referral"  # Referred by existing client
    CALCULATOR = "calculator"  # Used tax calculator
    DOCUMENT_UPLOAD = "document_upload"  # Uploaded return
    QUICK_ESTIMATE = "quick_estimate"  # Filled quick estimate form
    CAMPAIGN = "campaign"  # Marketing campaign
    DIRECT = "direct"  # Direct inquiry


class LeadStatus(str, Enum):
    """Status of the lead in the pipeline."""
    NEW = "new"  # Just created
    QUALIFIED = "qualified"  # Has potential savings
    CONTACTED = "contacted"  # CPA reached out
    ENGAGED = "engaged"  # Responded to outreach
    CONVERTED = "converted"  # Became a client
    LOST = "lost"  # Did not convert


class LeadPriority(str, Enum):
    """Priority level for lead follow-up."""
    HIGH = "high"  # High savings potential
    MEDIUM = "medium"  # Moderate savings potential
    LOW = "low"  # Lower priority


@dataclass
class ProspectLead:
    """
    A prospect lead generated through the platform.
    """
    lead_id: str
    source: LeadSource
    status: LeadStatus
    created_at: datetime

    # Contact info (required for full analysis)
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None

    # Tax profile (extracted or estimated)
    filing_status: Optional[FilingStatus] = None
    estimated_agi: Optional[Decimal] = None
    estimated_wages: Optional[Decimal] = None
    has_dependents: bool = False
    num_dependents: int = 0

    # Analysis preview (teaser)
    teaser_savings: Optional[Decimal] = None
    teaser_opportunities: List[str] = field(default_factory=list)

    # Full analysis (after contact info provided)
    full_analysis: Optional[InstantAnalysis] = None
    parsed_return: Optional[Parsed1040Data] = None

    # Assignment
    assigned_cpa_id: Optional[str] = None
    priority: LeadPriority = LeadPriority.MEDIUM

    # Conversion tracking
    converted_client_id: Optional[str] = None
    converted_at: Optional[datetime] = None

    # Notes
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "source": self.source.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "contact": {
                "email": self.email,
                "phone": self.phone,
                "name": self.name,
            },
            "tax_profile": {
                "filing_status": self.filing_status.value if self.filing_status else None,
                "estimated_agi": float(self.estimated_agi) if self.estimated_agi else None,
                "estimated_wages": float(self.estimated_wages) if self.estimated_wages else None,
                "has_dependents": self.has_dependents,
                "num_dependents": self.num_dependents,
            },
            "teaser": {
                "potential_savings": float(self.teaser_savings) if self.teaser_savings else None,
                "opportunities": self.teaser_opportunities,
            },
            "full_analysis": self.full_analysis.to_dict() if self.full_analysis else None,
            "assignment": {
                "cpa_id": self.assigned_cpa_id,
                "priority": self.priority.value,
            },
            "conversion": {
                "client_id": self.converted_client_id,
                "converted_at": self.converted_at.isoformat() if self.converted_at else None,
            },
            "notes": self.notes,
        }


@dataclass
class LeadTeaser:
    """
    Teaser shown to prospects before they provide contact info.

    Shows enough value to encourage conversion without giving
    away all the analysis details.
    """
    potential_savings_range: str  # e.g., "$2,000 - $4,000"
    opportunity_count: int
    opportunity_categories: List[str]
    headline: str
    call_to_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "potential_savings_range": self.potential_savings_range,
            "opportunity_count": self.opportunity_count,
            "opportunity_categories": self.opportunity_categories,
            "headline": self.headline,
            "call_to_action": self.call_to_action,
        }


class LeadGenerationService:
    """
    Service for generating and managing prospect leads.

    Supports multiple lead generation flows:
    1. Quick estimate (basic questions → teaser → contact capture)
    2. Document upload (1040 upload → teaser → contact capture)
    3. Calculator (specific calculation → teaser → contact capture)
    """

    def __init__(self):
        self._leads: Dict[str, ProspectLead] = {}
        self.onboarding_service = SmartOnboardingService()
        self.question_generator = AIQuestionGenerator()

    # =========================================================================
    # LEAD CREATION
    # =========================================================================

    def create_lead_from_quick_estimate(
        self,
        filing_status: str,
        estimated_income: float,
        has_dependents: bool = False,
        num_dependents: int = 0,
        source: LeadSource = LeadSource.QUICK_ESTIMATE,
    ) -> tuple[ProspectLead, LeadTeaser]:
        """
        Create a lead from a quick estimate form.

        This is the fastest path - just a few questions to generate
        a teaser that shows potential value.
        """
        # Map filing status
        status_map = {
            "single": FilingStatus.SINGLE,
            "mfj": FilingStatus.MARRIED_FILING_JOINTLY,
            "married_filing_jointly": FilingStatus.MARRIED_FILING_JOINTLY,
            "mfs": FilingStatus.MARRIED_FILING_SEPARATELY,
            "married_filing_separately": FilingStatus.MARRIED_FILING_SEPARATELY,
            "hoh": FilingStatus.HEAD_OF_HOUSEHOLD,
            "head_of_household": FilingStatus.HEAD_OF_HOUSEHOLD,
        }
        fs = status_map.get(filing_status.lower(), FilingStatus.SINGLE)

        # Create lead
        lead = ProspectLead(
            lead_id=str(uuid.uuid4()),
            source=source,
            status=LeadStatus.NEW,
            created_at=datetime.utcnow(),
            filing_status=fs,
            estimated_agi=Decimal(str(estimated_income)),
            estimated_wages=Decimal(str(estimated_income)),
            has_dependents=has_dependents,
            num_dependents=num_dependents,
        )

        # Generate teaser
        teaser = self._generate_teaser(lead)
        lead.teaser_savings = Decimal(str(self._parse_savings_range(teaser.potential_savings_range)[1]))
        lead.teaser_opportunities = teaser.opportunity_categories

        # Determine priority
        if lead.teaser_savings and lead.teaser_savings > Decimal("3000"):
            lead.priority = LeadPriority.HIGH
        elif lead.teaser_savings and lead.teaser_savings > Decimal("1000"):
            lead.priority = LeadPriority.MEDIUM
        else:
            lead.priority = LeadPriority.LOW

        self._leads[lead.lead_id] = lead
        logger.info(f"Created lead {lead.lead_id} from quick estimate")

        return lead, teaser

    async def create_lead_from_document(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = "application/pdf",
    ) -> tuple[ProspectLead, LeadTeaser]:
        """
        Create a lead from an uploaded 1040 document.

        This provides the most accurate teaser since we have
        actual tax return data.
        """
        # Start an onboarding session to process the document
        session = self.onboarding_service.start_onboarding("prospect")

        # Process document
        session = await self.onboarding_service.process_document(
            session_id=session.session_id,
            file_content=file_content,
            filename=filename,
            content_type=content_type,
        )

        if not session.parsed_1040:
            raise ValueError("Failed to extract data from document")

        parsed = session.parsed_1040

        # Create lead from parsed data
        lead = ProspectLead(
            lead_id=str(uuid.uuid4()),
            source=LeadSource.DOCUMENT_UPLOAD,
            status=LeadStatus.NEW,
            created_at=datetime.utcnow(),
            name=parsed.taxpayer_name,
            filing_status=parsed.filing_status,
            estimated_agi=parsed.adjusted_gross_income,
            estimated_wages=parsed.wages_salaries_tips,
            has_dependents=(parsed.total_dependents or 0) > 0,
            num_dependents=parsed.total_dependents or 0,
            parsed_return=parsed,
        )

        # Generate teaser from actual analysis
        teaser = self._generate_teaser_from_parsed(parsed)
        lead.teaser_savings = Decimal(str(self._parse_savings_range(teaser.potential_savings_range)[1]))
        lead.teaser_opportunities = teaser.opportunity_categories

        # Determine priority
        if lead.teaser_savings and lead.teaser_savings > Decimal("3000"):
            lead.priority = LeadPriority.HIGH
        elif lead.teaser_savings and lead.teaser_savings > Decimal("1000"):
            lead.priority = LeadPriority.MEDIUM
        else:
            lead.priority = LeadPriority.LOW

        self._leads[lead.lead_id] = lead
        logger.info(f"Created lead {lead.lead_id} from document upload")

        return lead, teaser

    # =========================================================================
    # LEAD CONVERSION
    # =========================================================================

    def capture_contact_info(
        self,
        lead_id: str,
        email: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> ProspectLead:
        """
        Capture contact information for a lead.

        Once contact info is provided, unlock the full analysis.
        """
        lead = self._leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        lead.email = email
        lead.name = name or lead.name
        lead.phone = phone
        lead.status = LeadStatus.QUALIFIED

        # Run full analysis now that we have contact info
        if lead.parsed_return:
            # Use actual parsed data
            lead.full_analysis = self._run_full_analysis_from_parsed(lead.parsed_return)
        else:
            # Estimate based on provided info
            lead.full_analysis = self._run_estimated_analysis(lead)

        logger.info(f"Captured contact info for lead {lead_id}: {email}")
        return lead

    def assign_lead_to_cpa(
        self,
        lead_id: str,
        cpa_id: str,
    ) -> ProspectLead:
        """
        Assign a lead to a CPA for follow-up.
        """
        lead = self._leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        lead.assigned_cpa_id = cpa_id
        lead.status = LeadStatus.CONTACTED if lead.status == LeadStatus.QUALIFIED else lead.status

        logger.info(f"Assigned lead {lead_id} to CPA {cpa_id}")
        return lead

    def convert_lead_to_client(
        self,
        lead_id: str,
        cpa_id: str,
    ) -> tuple[ProspectLead, str]:
        """
        Convert a qualified lead to a client.

        Returns the updated lead and the new client ID.
        """
        lead = self._leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        if not lead.email:
            raise ValueError("Lead must have contact info to convert")

        # Create client (would integrate with actual client service)
        client_id = str(uuid.uuid4())

        lead.status = LeadStatus.CONVERTED
        lead.converted_client_id = client_id
        lead.converted_at = datetime.utcnow()
        lead.assigned_cpa_id = cpa_id

        logger.info(f"Converted lead {lead_id} to client {client_id}")
        return lead, client_id

    def update_lead_status(
        self,
        lead_id: str,
        status: LeadStatus,
        note: Optional[str] = None,
    ) -> ProspectLead:
        """
        Update lead status with optional note.
        """
        lead = self._leads.get(lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        lead.status = status
        if note:
            lead.notes.append(f"[{datetime.utcnow().isoformat()}] {note}")

        return lead

    # =========================================================================
    # LEAD QUERIES
    # =========================================================================

    def get_lead(self, lead_id: str) -> Optional[ProspectLead]:
        """Get a lead by ID."""
        return self._leads.get(lead_id)

    def get_leads_for_cpa(
        self,
        cpa_id: str,
        status: Optional[LeadStatus] = None,
    ) -> List[ProspectLead]:
        """Get all leads assigned to a CPA."""
        leads = [l for l in self._leads.values() if l.assigned_cpa_id == cpa_id]
        if status:
            leads = [l for l in leads if l.status == status]
        return sorted(leads, key=lambda l: l.created_at, reverse=True)

    def get_unassigned_leads(self) -> List[ProspectLead]:
        """Get all unassigned leads."""
        return [
            l for l in self._leads.values()
            if l.assigned_cpa_id is None and l.status != LeadStatus.LOST
        ]

    def get_high_priority_leads(self) -> List[ProspectLead]:
        """Get all high priority leads."""
        return [
            l for l in self._leads.values()
            if l.priority == LeadPriority.HIGH and l.status not in [LeadStatus.CONVERTED, LeadStatus.LOST]
        ]

    def get_lead_pipeline_summary(self, cpa_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of the lead pipeline."""
        leads = list(self._leads.values())
        if cpa_id:
            leads = [l for l in leads if l.assigned_cpa_id == cpa_id]

        return {
            "total": len(leads),
            "by_status": {
                status.value: len([l for l in leads if l.status == status])
                for status in LeadStatus
            },
            "by_priority": {
                priority.value: len([l for l in leads if l.priority == priority])
                for priority in LeadPriority
            },
            "by_source": {
                source.value: len([l for l in leads if l.source == source])
                for source in LeadSource
            },
            "total_potential_savings": sum(
                float(l.teaser_savings or 0) for l in leads
                if l.status not in [LeadStatus.CONVERTED, LeadStatus.LOST]
            ),
            "conversion_rate": (
                len([l for l in leads if l.status == LeadStatus.CONVERTED]) /
                len(leads) * 100 if leads else 0
            ),
        }

    # =========================================================================
    # TEASER GENERATION
    # =========================================================================

    def _generate_teaser(self, lead: ProspectLead) -> LeadTeaser:
        """
        Generate a teaser based on estimated tax profile.

        The teaser shows enough to be compelling without giving
        away the detailed analysis.
        """
        opportunities = []
        min_savings = Decimal("0")
        max_savings = Decimal("0")

        agi = lead.estimated_agi or Decimal("0")
        fs = lead.filing_status

        # Retirement opportunity (almost everyone)
        if agi > Decimal("30000"):
            opportunities.append("Retirement Savings")
            marginal_rate = self._estimate_marginal_rate(agi, fs)
            # Assume they could contribute more to 401k/IRA
            potential = Decimal("10000") * marginal_rate
            min_savings += potential * Decimal("0.5")
            max_savings += potential

        # HSA opportunity (common)
        if agi > Decimal("40000"):
            opportunities.append("Healthcare Tax Benefits")
            marginal_rate = self._estimate_marginal_rate(agi, fs)
            hsa_savings = Decimal("4000") * marginal_rate
            min_savings += hsa_savings * Decimal("0.3")
            max_savings += hsa_savings

        # Dependent benefits
        if lead.has_dependents:
            opportunities.append("Family Tax Credits")
            per_child = Decimal("1000")
            min_savings += per_child * lead.num_dependents * Decimal("0.5")
            max_savings += per_child * lead.num_dependents

        # Deduction optimization
        if agi > Decimal("60000"):
            opportunities.append("Deduction Strategy")
            min_savings += Decimal("200")
            max_savings += Decimal("1500")

        # Generate range string
        savings_range = f"${float(min_savings):,.0f} - ${float(max_savings):,.0f}"

        # Generate headline
        if max_savings > Decimal("3000"):
            headline = "We found significant tax savings opportunities!"
        elif max_savings > Decimal("1000"):
            headline = "We identified potential ways to reduce your taxes."
        else:
            headline = "Let's see if we can optimize your tax situation."

        return LeadTeaser(
            potential_savings_range=savings_range,
            opportunity_count=len(opportunities),
            opportunity_categories=opportunities,
            headline=headline,
            call_to_action="Enter your email to see your personalized tax savings report.",
        )

    def _generate_teaser_from_parsed(self, parsed: Parsed1040Data) -> LeadTeaser:
        """
        Generate a teaser from actual parsed 1040 data.

        More accurate than estimated teaser.
        """
        opportunities = []
        min_savings = Decimal("0")
        max_savings = Decimal("0")

        agi = parsed.adjusted_gross_income or Decimal("0")
        wages = parsed.wages_salaries_tips or Decimal("0")
        fs = parsed.filing_status

        marginal_rate = self._estimate_marginal_rate(agi, fs)

        # Check retirement
        if wages > Decimal("30000"):
            opportunities.append("Retirement Optimization")
            # Assume room to increase contributions
            potential = Decimal("15000") * marginal_rate
            min_savings += potential * Decimal("0.3")
            max_savings += potential

        # Check HSA
        if wages > Decimal("40000"):
            opportunities.append("Healthcare Tax Benefits")
            hsa_max = Decimal("8300") if fs == FilingStatus.MARRIED_FILING_JOINTLY else Decimal("4150")
            hsa_savings = hsa_max * marginal_rate
            min_savings += hsa_savings * Decimal("0.2")
            max_savings += hsa_savings

        # Check dependents
        if parsed.total_dependents and parsed.total_dependents > 0:
            ctc = parsed.child_tax_credit or Decimal("0")
            if ctc < Decimal("2000") * parsed.total_dependents:
                opportunities.append("Child Tax Benefits")
                min_savings += Decimal("500") * parsed.total_dependents
                max_savings += Decimal("1500") * parsed.total_dependents

        # Check standard vs itemized
        std_ded = parsed.standard_deduction or Decimal("0")
        if std_ded > 0:
            opportunities.append("Deduction Strategy")
            min_savings += Decimal("200")
            max_savings += Decimal("1200")

        # Check credits
        if parsed.american_opportunity_credit == 0:
            opportunities.append("Education Credits")
            min_savings += Decimal("0")
            max_savings += Decimal("2500")

        savings_range = f"${float(min_savings):,.0f} - ${float(max_savings):,.0f}"

        if max_savings > Decimal("4000"):
            headline = f"Based on your {parsed.tax_year} return, we found significant savings!"
        elif max_savings > Decimal("1500"):
            headline = "Your tax situation has optimization potential."
        else:
            headline = "Let's explore your tax optimization options."

        return LeadTeaser(
            potential_savings_range=savings_range,
            opportunity_count=len(opportunities),
            opportunity_categories=opportunities,
            headline=headline,
            call_to_action="Enter your email to unlock your full personalized tax savings report.",
        )

    # =========================================================================
    # FULL ANALYSIS
    # =========================================================================

    def _run_full_analysis_from_parsed(self, parsed: Parsed1040Data) -> InstantAnalysis:
        """Run full analysis using parsed 1040 data."""
        # Use the smart onboarding service's analysis logic
        from .smart_onboarding_service import OnboardingSession, OnboardingStatus

        # Create a mock session
        session = OnboardingSession(
            session_id="analysis",
            cpa_id="lead_gen",
            status=OnboardingStatus.OCR_COMPLETE,
            created_at=datetime.utcnow(),
            parsed_1040=parsed,
        )

        # Default answers for common questions
        default_answers = {
            "retirement_401k_available": "yes_with_match",
            "retirement_401k_contribution": "6-10",
            "healthcare_hdhp": "yes",
            "healthcare_hsa": "partial",
        }

        if parsed.total_dependents and parsed.total_dependents > 0:
            default_answers["dependents_childcare"] = "yes_high"

        session.answers = default_answers

        # Run analysis
        return self.onboarding_service._run_instant_analysis(session)

    def _run_estimated_analysis(self, lead: ProspectLead) -> InstantAnalysis:
        """Run analysis based on estimated data when no return uploaded."""
        # Create mock parsed data
        parsed = Parsed1040Data(
            filing_status=lead.filing_status,
            adjusted_gross_income=lead.estimated_agi,
            wages_salaries_tips=lead.estimated_wages,
            total_dependents=lead.num_dependents if lead.has_dependents else 0,
        )

        return self._run_full_analysis_from_parsed(parsed)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _estimate_marginal_rate(
        self,
        agi: Optional[Decimal],
        filing_status: Optional[FilingStatus],
    ) -> Decimal:
        """Estimate marginal tax rate."""
        if not agi:
            return Decimal("0.22")

        agi_float = float(agi)

        if filing_status == FilingStatus.MARRIED_FILING_JOINTLY:
            if agi_float < 23200:
                return Decimal("0.10")
            elif agi_float < 94300:
                return Decimal("0.12")
            elif agi_float < 201050:
                return Decimal("0.22")
            elif agi_float < 383900:
                return Decimal("0.24")
            else:
                return Decimal("0.32")
        else:
            if agi_float < 11600:
                return Decimal("0.10")
            elif agi_float < 47150:
                return Decimal("0.12")
            elif agi_float < 100525:
                return Decimal("0.22")
            elif agi_float < 191950:
                return Decimal("0.24")
            else:
                return Decimal("0.32")

    def _parse_savings_range(self, range_str: str) -> tuple[float, float]:
        """Parse a savings range string like '$1,000 - $3,000'."""
        import re
        numbers = re.findall(r'[\d,]+', range_str)
        if len(numbers) >= 2:
            return (
                float(numbers[0].replace(",", "")),
                float(numbers[1].replace(",", "")),
            )
        elif len(numbers) == 1:
            val = float(numbers[0].replace(",", ""))
            return (val * 0.7, val)
        return (0.0, 0.0)


# Singleton instance
_lead_generation_service: Optional[LeadGenerationService] = None


def get_lead_generation_service() -> LeadGenerationService:
    """Get the singleton lead generation service instance."""
    global _lead_generation_service
    if _lead_generation_service is None:
        _lead_generation_service = LeadGenerationService()
    return _lead_generation_service
