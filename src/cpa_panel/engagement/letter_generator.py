"""
Engagement Letter Generator

Generates professional engagement letters from templates.
Designed for CPA-client tax advisory engagements.

Scope boundaries (enforced):
- Template-based generation only
- No contract negotiation workflow
- No version tracking (single letter per engagement)
- E-sign webhook integration, not full signing flow
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, date
import hashlib
import logging

logger = logging.getLogger(__name__)


class EngagementLetterType(str, Enum):
    """Types of engagement letters supported."""
    TAX_PREPARATION = "tax_preparation"
    TAX_ADVISORY = "tax_advisory"
    TAX_PLANNING = "tax_planning"
    AMENDED_RETURN = "amended_return"


@dataclass
class EngagementLetter:
    """Generated engagement letter."""
    letter_id: str
    letter_type: EngagementLetterType
    session_id: str
    tenant_id: str

    # Parties
    cpa_firm_name: str
    cpa_name: str
    cpa_credentials: str  # e.g., "CPA, MST"
    client_name: str
    client_email: str

    # Engagement details
    tax_year: int
    complexity_tier: str
    services_description: str
    fee_amount: float
    fee_description: str

    # Content
    letter_content: str

    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    content_hash: str = ""
    esign_status: str = "pending"  # pending, sent, signed, declined
    esign_envelope_id: Optional[str] = None
    signed_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute content hash for integrity verification."""
        content = f"{self.letter_content}:{self.cpa_name}:{self.client_name}:{self.fee_amount}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "letter_id": self.letter_id,
            "letter_type": self.letter_type.value,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "cpa_firm_name": self.cpa_firm_name,
            "cpa_name": self.cpa_name,
            "cpa_credentials": self.cpa_credentials,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "tax_year": self.tax_year,
            "complexity_tier": self.complexity_tier,
            "fee_amount": self.fee_amount,
            "fee_description": self.fee_description,
            "generated_at": self.generated_at.isoformat(),
            "content_hash": self.content_hash,
            "esign_status": self.esign_status,
            "esign_envelope_id": self.esign_envelope_id,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
        }


class EngagementLetterGenerator:
    """
    Generates engagement letters from templates.

    Scope: Template generation + e-sign webhook integration.
    NOT: Contract management, negotiation, versioning.
    """

    # Template for tax preparation engagement
    TAX_PREPARATION_TEMPLATE = """
{firm_name}
{firm_address}

{current_date}

{client_name}
{client_address}

RE: Engagement Letter for {tax_year} Tax Preparation Services

Dear {client_name}:

This letter confirms the terms of our engagement to prepare your {tax_year} federal and applicable state income tax returns.

SCOPE OF SERVICES

We will prepare your {tax_year} individual income tax return(s) based on information you provide. Our services include:

{services_list}

This engagement is classified as {complexity_tier} complexity based on your tax situation.

YOUR RESPONSIBILITIES

You are responsible for providing complete and accurate information necessary for the preparation of your tax returns. You represent that the information you provide is accurate and complete to the best of your knowledge.

You are responsible for:
- Providing all relevant tax documents (W-2s, 1099s, K-1s, etc.)
- Responding promptly to our requests for additional information
- Reviewing and approving the completed returns before filing
- Maintaining adequate records to support the items reported on your returns

FEES

Our fee for the services described above is {fee_amount}. {fee_description}

Payment is due upon completion of the engagement. We reserve the right to suspend services if payment is not received.

PROFESSIONAL STANDARDS

We will perform our services in accordance with applicable professional standards, including the Statements on Standards for Tax Services issued by the American Institute of Certified Public Accountants.

LIMITATIONS

Our engagement does not include:
- Audit, review, or compilation of financial statements
- Bookkeeping or accounting services
- Legal advice
- Investment or financial planning advice
- Representation before the IRS (unless separately engaged)

IRS CIRCULAR 230 DISCLOSURE

To ensure compliance with requirements imposed by the IRS, we inform you that any U.S. federal tax advice contained in this communication is not intended or written to be used, and cannot be used, for the purpose of (i) avoiding penalties under the Internal Revenue Code or (ii) promoting, marketing, or recommending to another party any transaction or matter addressed herein.

IMPORTANT: This engagement is for tax preparation advisory services only. Tax returns prepared through this engagement must be filed through IRS-authorized e-file channels or paper filing. This is not an e-filing service.

AGREEMENT

If you agree to the terms of this engagement, please sign below and return a copy to our office. Your signature indicates that you understand and agree to the terms described above.

We appreciate the opportunity to serve you.

Sincerely,

{cpa_name}, {cpa_credentials}
{firm_name}


ACCEPTED AND AGREED:

_________________________________
{client_name}

Date: _____________
"""

    TAX_ADVISORY_TEMPLATE = """
{firm_name}
{firm_address}

{current_date}

{client_name}
{client_address}

RE: Tax Advisory Engagement for {tax_year}

Dear {client_name}:

This letter confirms the terms of our engagement to provide tax advisory services for your {tax_year} tax situation.

SCOPE OF SERVICES

We will provide tax advisory services including:

{services_list}

This engagement is classified as {complexity_tier} complexity based on your tax situation.

ADVISORY NATURE OF SERVICES

This engagement is advisory in nature. We will analyze your tax situation and provide recommendations, but implementation decisions remain your responsibility. Our advice is based on current tax law and regulations, which may change.

YOUR RESPONSIBILITIES

You are responsible for:
- Providing complete and accurate financial information
- Informing us of any material changes to your situation
- Making final decisions on tax positions and strategies
- Implementing recommended strategies through appropriate channels

FEES

Our fee for the services described above is {fee_amount}. {fee_description}

LIMITATIONS

This engagement does not include:
- Tax return preparation (unless separately engaged)
- Legal advice or representation
- Investment advice or portfolio management
- Audit representation

IRS CIRCULAR 230 DISCLOSURE

To ensure compliance with requirements imposed by the IRS, we inform you that any U.S. federal tax advice contained in this communication is not intended or written to be used, and cannot be used, for the purpose of (i) avoiding penalties under the Internal Revenue Code or (ii) promoting, marketing, or recommending to another party any transaction or matter addressed herein.

AGREEMENT

If you agree to the terms of this engagement, please sign below.

Sincerely,

{cpa_name}, {cpa_credentials}
{firm_name}


ACCEPTED AND AGREED:

_________________________________
{client_name}

Date: _____________
"""

    def __init__(self):
        """Initialize letter generator."""
        self._templates = {
            EngagementLetterType.TAX_PREPARATION: self.TAX_PREPARATION_TEMPLATE,
            EngagementLetterType.TAX_ADVISORY: self.TAX_ADVISORY_TEMPLATE,
            EngagementLetterType.TAX_PLANNING: self.TAX_ADVISORY_TEMPLATE,  # Use advisory template
            EngagementLetterType.AMENDED_RETURN: self.TAX_PREPARATION_TEMPLATE,
        }

    def generate(
        self,
        session_id: str,
        tenant_id: str,
        letter_type: EngagementLetterType,
        cpa_firm_name: str,
        cpa_name: str,
        cpa_credentials: str,
        firm_address: str,
        client_name: str,
        client_email: str,
        client_address: str,
        tax_year: int,
        complexity_tier: str,
        services: List[str],
        fee_amount: float,
        fee_description: str = "",
    ) -> EngagementLetter:
        """
        Generate an engagement letter.

        Args:
            session_id: Tax return session ID
            tenant_id: Tenant/firm identifier
            letter_type: Type of engagement
            cpa_firm_name: Name of CPA firm
            cpa_name: CPA's name
            cpa_credentials: CPA's credentials (e.g., "CPA, MST")
            firm_address: Firm's address
            client_name: Client's name
            client_email: Client's email for e-sign
            client_address: Client's address
            tax_year: Tax year for engagement
            complexity_tier: Complexity tier name
            services: List of services included
            fee_amount: Engagement fee
            fee_description: Additional fee terms

        Returns:
            Generated EngagementLetter
        """
        template = self._templates.get(letter_type, self.TAX_PREPARATION_TEMPLATE)

        # Format services list
        services_list = "\n".join(f"  - {service}" for service in services)

        # Format fee
        fee_formatted = f"${fee_amount:,.2f}"
        if not fee_description:
            fee_description = "This fee is based on the complexity of your tax situation."

        # Generate content
        content = template.format(
            firm_name=cpa_firm_name,
            firm_address=firm_address,
            current_date=date.today().strftime("%B %d, %Y"),
            client_name=client_name,
            client_address=client_address,
            tax_year=tax_year,
            services_list=services_list,
            complexity_tier=complexity_tier,
            fee_amount=fee_formatted,
            fee_description=fee_description,
            cpa_name=cpa_name,
            cpa_credentials=cpa_credentials,
        )

        # Generate letter ID
        letter_id = f"EL-{session_id[:8]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        return EngagementLetter(
            letter_id=letter_id,
            letter_type=letter_type,
            session_id=session_id,
            tenant_id=tenant_id,
            cpa_firm_name=cpa_firm_name,
            cpa_name=cpa_name,
            cpa_credentials=cpa_credentials,
            client_name=client_name,
            client_email=client_email,
            tax_year=tax_year,
            complexity_tier=complexity_tier,
            services_description="; ".join(services),
            fee_amount=fee_amount,
            fee_description=fee_description,
            letter_content=content,
        )

    def get_services_for_complexity(
        self,
        complexity_tier: str,
        letter_type: EngagementLetterType = EngagementLetterType.TAX_PREPARATION,
    ) -> List[str]:
        """Get default services list based on complexity tier."""
        base_services = [
            "Preparation of federal Form 1040 individual income tax return",
            "Review of tax documents for accuracy and completeness",
            "Calculation of tax liability or refund",
            "Electronic filing coordination through your chosen e-file provider",
        ]

        tier_services = {
            "tier_1_simple": [],
            "tier_2_moderate": [
                "Preparation of Schedule A (Itemized Deductions) if beneficial",
                "Preparation of Schedule B (Interest and Dividends)",
                "Preparation of Schedule D (Capital Gains and Losses)",
                "Analysis of itemized vs. standard deduction",
            ],
            "tier_3_complex": [
                "Preparation of Schedule C (Self-Employment Income)",
                "Preparation of Schedule E (Rental and Royalty Income)",
                "Preparation of Schedule SE (Self-Employment Tax)",
                "Preparation of Form 8995 (QBI Deduction)",
                "Depreciation calculations and Form 4562",
                "Estimated tax payment recommendations",
            ],
            "tier_4_highly_complex": [
                "Multi-state tax return preparation",
                "Foreign income reporting and Form 1116",
                "Alternative Minimum Tax analysis (Form 6251)",
                "Stock option reporting (Forms 3921/3922)",
                "Passive activity loss calculations (Form 8582)",
                "Cryptocurrency transaction reporting",
            ],
            "tier_5_enterprise": [
                "Comprehensive multi-entity tax coordination",
                "Estate and gift tax planning coordination",
                "International tax compliance (FBAR, Form 8938)",
                "Charitable giving strategy optimization",
                "Year-round tax planning advisory",
            ],
        }

        additional = tier_services.get(complexity_tier.lower().replace(" ", "_").replace("-", "_"), [])

        if letter_type == EngagementLetterType.TAX_ADVISORY:
            base_services = [
                "Analysis of your current tax situation",
                "Identification of tax optimization opportunities",
                "Recommendations for tax-efficient strategies",
                "Written summary of findings and recommendations",
            ]

        return base_services + additional
