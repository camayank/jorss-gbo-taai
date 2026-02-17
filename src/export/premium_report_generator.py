"""
CA4CPA GLOBAL LLC - Premium Report Generator

Single orchestrator for generating tiered tax advisory reports.

Tier Model:
- BASIC (free): Tax summary + computation statement
- STANDARD ($79): + Advisory sections + scenarios
- PREMIUM ($199): + Full appendices + PDF artifact + action items

Design Rules:
1. Tier = section whitelist (no conditional logic inside engines)
2. Single orchestration call: generate(session_id, tier, format)
3. Same intelligence for direct_client and firm_client

Usage:
    from export.premium_report_generator import PremiumReportGenerator, ReportTier
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

    generator = PremiumReportGenerator()
    report = generator.generate(session_id="abc123", tier=ReportTier.PREMIUM, format="html")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, FrozenSet, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from uuid import UUID
import logging

if TYPE_CHECKING:
    from models.tax_return import TaxReturn

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS
# =============================================================================

class ReportTier(str, Enum):
    """Report tier levels."""
    BASIC = "basic"         # Free tier
    STANDARD = "standard"   # $79
    PREMIUM = "premium"     # $199


class ReportFormat(str, Enum):
    """Output formats."""
    HTML = "html"           # For client portal UI
    PDF = "pdf"             # For download artifact
    JSON = "json"           # For API consumption


class ReportSection(str, Enum):
    """All possible report sections."""
    # Core sections (Basic tier)
    TAX_SUMMARY = "tax_summary"
    COMPUTATION_STATEMENT = "computation_statement"
    DRAFT_RETURN = "draft_return"  # Deprecated: kept for backward compatibility only

    # Advisory sections (Standard tier)
    EXECUTIVE_SUMMARY = "executive_summary"
    CREDIT_ANALYSIS = "credit_analysis"
    DEDUCTION_ANALYSIS = "deduction_analysis"
    FILING_STATUS_ANALYSIS = "filing_status_analysis"
    RETIREMENT_OPTIMIZATION = "retirement_optimization"
    SCENARIO_COMPARISON = "scenario_comparison"

    # Premium sections
    ENTITY_STRUCTURE = "entity_structure"
    INVESTMENT_TAX_ANALYSIS = "investment_tax_analysis"
    MULTI_YEAR_PROJECTION = "multi_year_projection"
    ACTION_ITEMS = "action_items"

    # Appendices (Premium tier)
    APPENDIX_ASSUMPTIONS = "appendix_assumptions"
    APPENDIX_IRC_CITATIONS = "appendix_irc_citations"
    APPENDIX_CALCULATIONS = "appendix_calculations"

    # Always included
    DISCLAIMER = "disclaimer"


# =============================================================================
# TIER WHITELISTS
# =============================================================================

TIER_SECTIONS: Dict[ReportTier, FrozenSet[ReportSection]] = {
    ReportTier.BASIC: frozenset([
        ReportSection.TAX_SUMMARY,
        ReportSection.COMPUTATION_STATEMENT,
        ReportSection.DISCLAIMER,
    ]),

    ReportTier.STANDARD: frozenset([
        # Basic sections
        ReportSection.TAX_SUMMARY,
        ReportSection.COMPUTATION_STATEMENT,
        # Advisory sections
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.CREDIT_ANALYSIS,
        ReportSection.DEDUCTION_ANALYSIS,
        ReportSection.FILING_STATUS_ANALYSIS,
        ReportSection.RETIREMENT_OPTIMIZATION,
        ReportSection.SCENARIO_COMPARISON,
        ReportSection.DISCLAIMER,
    ]),

    ReportTier.PREMIUM: frozenset([
        # All Basic + Standard sections
        ReportSection.TAX_SUMMARY,
        ReportSection.COMPUTATION_STATEMENT,
        ReportSection.EXECUTIVE_SUMMARY,
        ReportSection.CREDIT_ANALYSIS,
        ReportSection.DEDUCTION_ANALYSIS,
        ReportSection.FILING_STATUS_ANALYSIS,
        ReportSection.RETIREMENT_OPTIMIZATION,
        ReportSection.SCENARIO_COMPARISON,
        # Premium-only sections
        ReportSection.ENTITY_STRUCTURE,
        ReportSection.INVESTMENT_TAX_ANALYSIS,
        ReportSection.MULTI_YEAR_PROJECTION,
        ReportSection.ACTION_ITEMS,
        # Appendices
        ReportSection.APPENDIX_ASSUMPTIONS,
        ReportSection.APPENDIX_IRC_CITATIONS,
        ReportSection.APPENDIX_CALCULATIONS,
        ReportSection.DISCLAIMER,
    ]),
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SectionContent:
    """Content for a single report section."""
    section_id: ReportSection
    title: str
    content: Dict[str, Any]
    html: str = ""
    order: int = 0


@dataclass
class ActionItem:
    """A prioritized action item."""
    action_id: str
    title: str
    description: str
    priority: int  # 1 = highest
    category: str  # tax_savings, compliance, planning
    potential_savings: float = 0.0
    deadline: Optional[str] = None
    irs_reference: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "category": self.category,
            "potential_savings": self.potential_savings,
            "deadline": self.deadline,
            "irs_reference": self.irs_reference,
        }


@dataclass
class GeneratedReport:
    """Complete generated report."""
    report_id: str
    session_id: str
    tier: ReportTier
    format: ReportFormat
    generated_at: str
    taxpayer_name: str
    tax_year: int
    sections: List[SectionContent]
    action_items: List[ActionItem]
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Output based on format
    html_content: str = ""
    pdf_bytes: bytes = b""
    json_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "session_id": self.session_id,
            "tier": self.tier.value,
            "format": self.format.value,
            "generated_at": self.generated_at,
            "taxpayer_name": self.taxpayer_name,
            "tax_year": self.tax_year,
            "section_count": len(self.sections),
            "action_item_count": len(self.action_items),
            "metadata": self.metadata,
        }


# =============================================================================
# SECTION METADATA
# =============================================================================

SECTION_METADATA: Dict[ReportSection, Dict[str, Any]] = {
    ReportSection.TAX_SUMMARY: {
        "title": "Tax Advisory Summary",
        "order": 1,
        "description": "Current tax position and planning baseline",
    },
    ReportSection.COMPUTATION_STATEMENT: {
        "title": "Computation Transparency",
        "order": 2,
        "description": "Traceable tax computation and assumptions",
    },
    ReportSection.DRAFT_RETURN: {
        "title": "Draft Tax Return (Deprecated)",
        "order": 3,
        "description": "Return-preparation output is not included in advisory reports",
    },
    ReportSection.EXECUTIVE_SUMMARY: {
        "title": "Executive Summary",
        "order": 4,
        "description": "Key findings and recommendations",
    },
    ReportSection.CREDIT_ANALYSIS: {
        "title": "Tax Credit Analysis",
        "order": 5,
        "description": "Credits you qualify for",
    },
    ReportSection.DEDUCTION_ANALYSIS: {
        "title": "Deduction Analysis",
        "order": 6,
        "description": "Standard vs itemized comparison",
    },
    ReportSection.FILING_STATUS_ANALYSIS: {
        "title": "Filing Status Optimization",
        "order": 7,
        "description": "Optimal filing status recommendation",
    },
    ReportSection.RETIREMENT_OPTIMIZATION: {
        "title": "Retirement Contribution Strategy",
        "order": 8,
        "description": "401(k), IRA, and HSA optimization",
    },
    ReportSection.SCENARIO_COMPARISON: {
        "title": "What-If Scenarios",
        "order": 9,
        "description": "Tax impact of different choices",
    },
    ReportSection.ENTITY_STRUCTURE: {
        "title": "Entity Structure Analysis",
        "order": 10,
        "description": "S-Corp, LLC, and business entity optimization",
    },
    ReportSection.INVESTMENT_TAX_ANALYSIS: {
        "title": "Investment Tax Planning",
        "order": 11,
        "description": "Capital gains, dividends, and tax-loss harvesting",
    },
    ReportSection.MULTI_YEAR_PROJECTION: {
        "title": "Multi-Year Tax Projection",
        "order": 12,
        "description": "3-year forward tax estimates",
    },
    ReportSection.ACTION_ITEMS: {
        "title": "Prioritized Action Items",
        "order": 13,
        "description": "Steps to optimize your taxes",
    },
    ReportSection.APPENDIX_ASSUMPTIONS: {
        "title": "Appendix A: Assumptions & Data Sources",
        "order": 20,
        "description": "Data inputs and confidence levels",
    },
    ReportSection.APPENDIX_IRC_CITATIONS: {
        "title": "Appendix B: IRC Citations & References",
        "order": 21,
        "description": "Legal basis for recommendations",
    },
    ReportSection.APPENDIX_CALCULATIONS: {
        "title": "Appendix C: Detailed Calculations",
        "order": 22,
        "description": "Line-by-line computation detail",
    },
    ReportSection.DISCLAIMER: {
        "title": "Disclaimer",
        "order": 99,
        "description": "Legal disclaimer",
    },
}


# =============================================================================
# LEGAL DISCLAIMERS
# =============================================================================

LEGAL_DISCLAIMERS = {
    "standard": """
DISCLAIMER

This tax advisory report is provided for informational purposes only and does not
constitute legal, tax, or accounting advice. The information contained herein is based
on the data provided and current tax laws as of the report date.

Tax laws are subject to change, and the application of tax laws to specific situations
may vary. We recommend consulting with a qualified tax professional before making any
tax-related decisions.

The calculations and recommendations in this report are based on the information
provided and may not reflect your complete financial situation. Actual tax liability
may differ based on factors not included in this analysis.

CA4CPA Global LLC and its affiliates are not responsible for any actions taken or not
taken based on this report.

This report is confidential and intended solely for the individual(s) named herein.
""",
    "irs_circular_230": """
IRS CIRCULAR 230 DISCLOSURE

To ensure compliance with requirements imposed by the IRS, we inform you that any
U.S. federal tax advice contained in this communication (including any attachments)
is not intended or written to be used, and cannot be used, for the purpose of:
(i) avoiding penalties under the Internal Revenue Code, or
(ii) promoting, marketing, or recommending to another party any transaction or matter
addressed herein.
""",
}


# =============================================================================
# PREMIUM REPORT GENERATOR
# =============================================================================

class PremiumReportGenerator:
    """
    Single orchestrator for generating tiered tax advisory reports.

    Implements the two design rules:
    1. Tier = section whitelist (no conditional logic inside engines)
    2. Single orchestration call: generate(session_id, tier, format)
    """

    def __init__(self):
        """Initialize the report generator."""
        self._tax_return_adapter = None
        self._computation_generator = None
        self._draft_generator = None
        self._advisory_service = None
        self._scenario_service = None
        self._pdf_generator = None

    # =========================================================================
    # LAZY-LOADED ADAPTERS
    # =========================================================================

    @property
    def tax_return_adapter(self):
        """Lazy load tax return adapter."""
        if self._tax_return_adapter is None:
            try:
                from cpa_panel.adapters import TaxReturnAdapter
                self._tax_return_adapter = TaxReturnAdapter()
            except ImportError:
                logger.warning("TaxReturnAdapter not available")
        return self._tax_return_adapter

    @property
    def computation_generator(self):
        """Lazy load computation statement generator."""
        if self._computation_generator is None:
            try:
                from export.computation_statement import TaxComputationStatement
                self._computation_generator = TaxComputationStatement
            except ImportError:
                logger.warning("TaxComputationStatement not available")
        return self._computation_generator

    @property
    def draft_generator(self):
        """Lazy load draft return generator."""
        if self._draft_generator is None:
            try:
                from export.draft_return import DraftReturnGenerator
                self._draft_generator = DraftReturnGenerator()
            except ImportError:
                logger.warning("DraftReturnGenerator not available")
        return self._draft_generator

    @property
    def advisory_service(self):
        """Lazy load advisory report service."""
        if self._advisory_service is None:
            try:
                from cpa_panel.services.advisory_report_service import AdvisoryReportService
                self._advisory_service = AdvisoryReportService()
            except ImportError:
                logger.warning("AdvisoryReportService not available")
        return self._advisory_service

    @property
    def scenario_service(self):
        """Lazy load scenario service."""
        if self._scenario_service is None:
            try:
                from cpa_panel.services.scenario_service import ScenarioService
                self._scenario_service = ScenarioService()
            except ImportError:
                logger.warning("ScenarioService not available")
        return self._scenario_service

    @property
    def pdf_generator(self):
        """Lazy load PDF generator."""
        if self._pdf_generator is None:
            try:
                from export.pdf_generator import TaxReturnPDFGenerator
                self._pdf_generator = TaxReturnPDFGenerator()
            except ImportError:
                logger.warning("TaxReturnPDFGenerator not available")
        return self._pdf_generator

    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================

    def generate(
        self,
        session_id: str,
        tier: ReportTier = ReportTier.BASIC,
        format: ReportFormat = ReportFormat.HTML,
        brand_context: Optional[Dict[str, Any]] = None,
    ) -> GeneratedReport:
        """
        Generate a tax advisory report.

        Single orchestration call that:
        1. Retrieves tax return data
        2. Determines sections based on tier whitelist
        3. Generates each section
        4. Prioritizes action items (Premium only)
        5. Renders to requested format

        Args:
            session_id: Client session identifier
            tier: Report tier (BASIC, STANDARD, PREMIUM)
            format: Output format (HTML, PDF, JSON)

        Returns:
            GeneratedReport with all content
        """
        import uuid

        report_id = str(uuid.uuid4())[:8]
        generated_at = datetime.utcnow().isoformat()

        # Get tax return
        tax_return = self._get_tax_return(session_id)
        if not tax_return:
            return self._error_report(
                report_id, session_id, tier, format,
                f"Tax return not found for session {session_id}"
            )

        # Get taxpayer info
        taxpayer_name = self._get_taxpayer_name(tax_return)
        tax_year = 2025  # Current tax year

        # Resolve branding context (white-label safe defaults).
        brand_context = brand_context or {}
        brand_name = (
            brand_context.get("platform_name")
            or brand_context.get("company_name")
            or "Tax Advisory Platform"
        )

        # Get sections for this tier
        allowed_sections = TIER_SECTIONS[tier]

        # Generate all sections
        sections: List[SectionContent] = []
        for section in ReportSection:
            if section in allowed_sections:
                section_content = self._generate_section(
                    section, tax_return, session_id
                )
                if section_content:
                    sections.append(section_content)

        # Sort by order
        sections.sort(key=lambda s: SECTION_METADATA.get(s.section_id, {}).get("order", 50))

        # Generate action items (Premium only)
        action_items: List[ActionItem] = []
        if tier == ReportTier.PREMIUM:
            action_items = self._generate_action_items(tax_return, session_id)

        # Create report
        report = GeneratedReport(
            report_id=report_id,
            session_id=session_id,
            tier=tier,
            format=format,
            generated_at=generated_at,
            taxpayer_name=taxpayer_name,
            tax_year=tax_year,
            sections=sections,
            action_items=action_items,
            metadata={
                "section_count": len(sections),
                "action_item_count": len(action_items),
                "tier_sections": [s.value for s in allowed_sections],
                "brand_name": brand_name,
            },
        )

        # Render to requested format
        if format == ReportFormat.HTML:
            report.html_content = self._render_html(report)
        elif format == ReportFormat.PDF:
            report.pdf_bytes = self._render_pdf(report)
        elif format == ReportFormat.JSON:
            report.json_data = self._render_json(report)

        logger.info(
            f"Generated {tier.value} report ({format.value}) for session {session_id}: "
            f"{len(sections)} sections, {len(action_items)} action items"
        )

        return report

    # =========================================================================
    # SECTION GENERATORS
    # =========================================================================

    def _generate_section(
        self,
        section: ReportSection,
        tax_return: "TaxReturn",
        session_id: str,
    ) -> Optional[SectionContent]:
        """Generate content for a single section."""

        metadata = SECTION_METADATA.get(section, {})
        title = metadata.get("title", section.value)
        order = metadata.get("order", 50)

        try:
            content: Dict[str, Any] = {}

            if section == ReportSection.TAX_SUMMARY:
                content = self._build_tax_summary(tax_return)

            elif section == ReportSection.COMPUTATION_STATEMENT:
                content = self._build_computation_statement(tax_return)

            elif section == ReportSection.DRAFT_RETURN:
                content = self._build_draft_return(tax_return)

            elif section == ReportSection.EXECUTIVE_SUMMARY:
                content = self._build_executive_summary(tax_return, session_id)

            elif section == ReportSection.CREDIT_ANALYSIS:
                content = self._build_credit_analysis(session_id)

            elif section == ReportSection.DEDUCTION_ANALYSIS:
                content = self._build_deduction_analysis(session_id)

            elif section == ReportSection.FILING_STATUS_ANALYSIS:
                content = self._build_filing_status_analysis(session_id)

            elif section == ReportSection.RETIREMENT_OPTIMIZATION:
                content = self._build_retirement_optimization(tax_return, session_id)

            elif section == ReportSection.SCENARIO_COMPARISON:
                content = self._build_scenario_comparison(tax_return, session_id)

            elif section == ReportSection.ENTITY_STRUCTURE:
                content = self._build_entity_structure(tax_return, session_id)

            elif section == ReportSection.INVESTMENT_TAX_ANALYSIS:
                content = self._build_investment_analysis(tax_return, session_id)

            elif section == ReportSection.MULTI_YEAR_PROJECTION:
                content = self._build_multi_year_projection(tax_return)

            elif section == ReportSection.ACTION_ITEMS:
                # Action items handled separately
                content = {"note": "See prioritized action items section"}

            elif section == ReportSection.APPENDIX_ASSUMPTIONS:
                content = self._build_assumptions_appendix(tax_return)

            elif section == ReportSection.APPENDIX_IRC_CITATIONS:
                content = self._build_irc_citations_appendix()

            elif section == ReportSection.APPENDIX_CALCULATIONS:
                content = self._build_calculations_appendix(tax_return)

            elif section == ReportSection.DISCLAIMER:
                content = {
                    "text": LEGAL_DISCLAIMERS["standard"],
                    "circular_230": LEGAL_DISCLAIMERS["irs_circular_230"],
                }

            return SectionContent(
                section_id=section,
                title=title,
                content=content,
                order=order,
            )

        except Exception as e:
            logger.error(f"Error generating section {section.value}: {e}")
            return None

    # =========================================================================
    # SECTION BUILDERS
    # =========================================================================

    def _build_tax_summary(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Build tax summary section."""
        agi = tax_return.adjusted_gross_income or 0
        taxable = tax_return.taxable_income or 0
        tax_liability = tax_return.tax_liability or 0
        refund_or_owed = tax_return.refund_or_owed or 0

        # Get withholding
        income = tax_return.income
        withholding = getattr(income, 'federal_withholding', 0) or 0

        # Calculate effective rate
        effective_rate = (tax_liability / agi * 100) if agi > 0 else 0

        return {
            "adjusted_gross_income": agi,
            "taxable_income": taxable,
            "tax_liability": tax_liability,
            "total_withholding": withholding,
            "refund_or_owed": refund_or_owed,
            "result_type": "refund" if refund_or_owed > 0 else "owed",
            "effective_tax_rate": float(money(effective_rate)),
            "filing_status": self._get_filing_status(tax_return),
        }

    def _build_computation_statement(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Build computation statement section."""
        if self.computation_generator:
            try:
                statement = self.computation_generator(tax_return)
                return statement.generate()
            except Exception as e:
                logger.error(f"Computation statement error: {e}")

        # Fallback: basic computation
        return {
            "parts": [
                {
                    "title": "Part I - Gross Income",
                    "lines": [
                        {"description": "Total Income", "amount": tax_return.adjusted_gross_income or 0}
                    ]
                }
            ]
        }

    def _build_draft_return(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Return advisory-safe placeholder for deprecated return-prep output."""
        return {
            "status": "disabled",
            "note": "Draft return generation is intentionally excluded from advisory reports.",
        }

    def _build_executive_summary(
        self, tax_return: "TaxReturn", session_id: str
    ) -> Dict[str, Any]:
        """Build executive summary section."""
        agi = tax_return.adjusted_gross_income or 0
        tax_liability = tax_return.tax_liability or 0
        refund_or_owed = tax_return.refund_or_owed or 0

        # Key findings
        findings = []

        # Check deduction type
        if hasattr(tax_return, 'deduction_type'):
            if tax_return.deduction_type == 'standard':
                findings.append("You're using the standard deduction")
            else:
                findings.append("Itemizing provides greater tax benefit")

        # Check refund/owed
        if refund_or_owed > 0:
            findings.append(f"You're receiving a refund of ${refund_or_owed:,.2f}")
        else:
            findings.append(f"You owe ${abs(refund_or_owed):,.2f} to the IRS")

        # Effective rate analysis
        effective_rate = (tax_liability / agi * 100) if agi > 0 else 0
        if effective_rate < 15:
            findings.append(f"Your effective tax rate ({effective_rate:.1f}%) is below average")

        return {
            "key_findings": findings,
            "summary_metrics": {
                "total_income": agi,
                "total_tax": tax_liability,
                "effective_rate": float(money(effective_rate)),
                "refund_or_owed": refund_or_owed,
            },
            "recommendations_count": 0,  # Will be populated by action items
        }

    def _build_credit_analysis(self, session_id: str) -> Dict[str, Any]:
        """Build credit analysis section using optimizer."""
        if self.advisory_service:
            try:
                optimizer = self.advisory_service.optimizer_adapter
                if optimizer:
                    result = optimizer.get_credit_analysis(session_id)
                    if result.success:
                        return {
                            **(result.data or {}),
                            "summary": result.summary,
                            "potential_savings": result.total_potential_savings,
                            "recommendations": result.recommendations,
                            "warnings": result.warnings,
                        }
            except Exception as e:
                logger.error(f"Credit analysis error: {e}")

        return {
            "credits_claimed": [],
            "credits_available": [],
            "potential_savings": 0,
        }

    def _build_deduction_analysis(self, session_id: str) -> Dict[str, Any]:
        """Build deduction analysis section."""
        if self.advisory_service:
            try:
                optimizer = self.advisory_service.optimizer_adapter
                if optimizer:
                    result = optimizer.get_deduction_analysis(session_id)
                    if result.success:
                        return {
                            **(result.data or {}),
                            "summary": result.summary,
                            "potential_savings": result.total_potential_savings,
                            "recommendations": result.recommendations,
                            "warnings": result.warnings,
                        }
            except Exception as e:
                logger.error(f"Deduction analysis error: {e}")

        return {
            "standard_deduction": 0,
            "itemized_total": 0,
            "recommended": "standard",
            "itemized_breakdown": [],
        }

    def _build_filing_status_analysis(self, session_id: str) -> Dict[str, Any]:
        """Build filing status analysis section."""
        if self.advisory_service:
            try:
                optimizer = self.advisory_service.optimizer_adapter
                if optimizer:
                    result = optimizer.get_filing_status_comparison(session_id)
                    if result.success:
                        return {
                            **(result.data or {}),
                            "summary": result.summary,
                            "potential_savings": result.total_potential_savings,
                            "recommendations": result.recommendations,
                            "warnings": result.warnings,
                        }
            except Exception as e:
                logger.error(f"Filing status error: {e}")

        return {
            "current_status": "unknown",
            "optimal_status": "unknown",
            "comparison": [],
        }

    def _build_retirement_optimization(
        self, tax_return: "TaxReturn", session_id: str
    ) -> Dict[str, Any]:
        """Build retirement optimization section."""
        if self.advisory_service:
            try:
                optimizer = self.advisory_service.optimizer_adapter
                if optimizer:
                    strategy = optimizer.get_full_strategy(session_id)
                    if strategy.success:
                        retirement = (strategy.data or {}).get("retirement_analysis", {})
                        return {
                            **retirement,
                            "summary": strategy.summary,
                            "potential_savings": strategy.total_potential_savings,
                            "recommendations": strategy.recommendations,
                            "warnings": strategy.warnings,
                        }
            except Exception as e:
                logger.error(f"Retirement strategy error: {e}")

        income = tax_return.income

        # Get current contributions
        current_401k = self._estimate_401k_contribution(tax_return)
        current_ira = self._estimate_ira_contribution(tax_return)
        current_hsa = self._estimate_hsa_contribution(tax_return)

        # 2025 limits
        limits = {
            "401k": 23500,
            "401k_catchup": 31000,  # Age 50+
            "ira": 7000,
            "ira_catchup": 8000,
            "hsa_individual": 4300,
            "hsa_family": 8550,
        }

        return {
            "current_contributions": {
                "401k": current_401k,
                "ira": current_ira,
                "hsa": current_hsa,
            },
            "limits_2025": limits,
            "available_space": {
                "401k": max(0, limits["401k"] - current_401k),
                "ira": max(0, limits["ira"] - current_ira),
                "hsa": max(0, limits["hsa_individual"] - current_hsa),
            },
            "tax_savings_potential": {
                "max_401k": (limits["401k"] - current_401k) * 0.22,  # Est. marginal rate
                "max_ira": (limits["ira"] - current_ira) * 0.22,
            },
        }

    def _build_scenario_comparison(
        self, tax_return: "TaxReturn", session_id: str
    ) -> Dict[str, Any]:
        """Build scenario comparison section."""
        if self.scenario_service:
            try:
                # Run standard scenarios
                scenario_templates = [
                    "max_401k",
                    "max_ira",
                    "charitable_bunching",
                ]

                results = self.scenario_service.compare_from_templates(
                    session_id=session_id,
                    template_ids=scenario_templates,
                )

                if results.get("success"):
                    comparison = results.get("comparison", {})
                    return {
                        "baseline": {
                            "tax_liability": tax_return.tax_liability or 0,
                            "refund_or_owed": tax_return.refund_or_owed or 0,
                        },
                        "scenarios": results.get("scenarios", []),
                        "best_scenario": comparison.get("best_scenario"),
                        "max_savings": comparison.get("max_savings", 0),
                        "analysis_timestamp": results.get("analysis_timestamp"),
                    }

                return {
                    "baseline": {"tax_liability": tax_return.tax_liability or 0},
                    "scenarios": [],
                    "error": results.get("error", "Scenario analysis unavailable"),
                }
            except Exception as e:
                logger.error(f"Scenario comparison error: {e}")

        return {
            "baseline": {"tax_liability": tax_return.tax_liability or 0},
            "scenarios": [],
            "note": "Run what-if scenarios to see potential savings",
        }

    def _build_entity_structure(
        self, tax_return: "TaxReturn", session_id: str
    ) -> Dict[str, Any]:
        """Build entity structure analysis (Premium)."""
        if self.advisory_service:
            try:
                optimizer = self.advisory_service.optimizer_adapter
                if optimizer:
                    result = optimizer.get_entity_comparison(session_id)
                    if result.success:
                        return {
                            **(result.data or {}),
                            "summary": result.summary,
                            "potential_savings": result.total_potential_savings,
                            "recommendations": result.recommendations,
                            "warnings": result.warnings,
                        }
            except Exception as e:
                logger.error(f"Entity structure optimization error: {e}")

        income = tax_return.income
        se_income = getattr(income, 'self_employment_income', 0) or 0

        if se_income < 50000:
            return {
                "recommendation": "sole_proprietorship",
                "reason": "Self-employment income below S-Corp threshold",
                "analysis": "S-Corp election typically beneficial above $50,000 net SE income",
            }

        # Calculate S-Corp savings
        reasonable_salary = min(se_income * 0.6, 150000)
        se_tax_current = se_income * 0.9235 * 0.153
        se_tax_scorp = reasonable_salary * 0.0765  # Employer portion
        savings = se_tax_current - se_tax_scorp

        return {
            "current_structure": "sole_proprietorship",
            "recommended_structure": "s_corporation" if savings > 5000 else "sole_proprietorship",
            "self_employment_income": se_income,
            "reasonable_salary": reasonable_salary,
            "potential_se_tax_savings": max(0, savings),
            "qbi_deduction_impact": "S-Corp may limit QBI deduction for specified service trades",
            "considerations": [
                "State filing requirements",
                "Payroll administration costs",
                "Reasonable compensation rules",
            ],
        }

    def _build_investment_analysis(self, tax_return: "TaxReturn", session_id: str) -> Dict[str, Any]:
        """Build investment tax analysis (Premium)."""
        if self.advisory_service:
            try:
                optimizer = self.advisory_service.optimizer_adapter
                if optimizer:
                    result = optimizer.get_full_strategy(session_id)
                    if result.success:
                        investment = (result.data or {}).get("investment_analysis", {})
                        if investment:
                            return {
                                **investment,
                                "summary": result.summary,
                                "recommendations": result.recommendations,
                                "warnings": result.warnings,
                            }
            except Exception:
                # Fall through to deterministic local summary.
                pass

        income = tax_return.income

        dividends = getattr(income, 'dividend_income', 0) or 0
        qualified_dividends = getattr(income, 'qualified_dividends', 0) or 0
        cap_gains = getattr(income, 'capital_gain_income', 0) or 0
        cap_losses = getattr(income, 'capital_losses', 0) or 0

        return {
            "dividend_income": dividends,
            "qualified_dividends": qualified_dividends,
            "qualified_rate": "0%, 15%, or 20% based on income",
            "capital_gains": cap_gains,
            "capital_losses": cap_losses,
            "net_capital_gain": cap_gains - min(cap_losses, 3000),
            "loss_carryforward": max(0, cap_losses - cap_gains - 3000),
            "tax_loss_harvesting_opportunity": cap_gains > 0 and cap_losses < cap_gains,
            "niit_threshold": 200000,  # Single
            "niit_applies": (tax_return.adjusted_gross_income or 0) > 200000,
        }

    def _build_multi_year_projection(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Build multi-year projection (Premium)."""
        try:
            from projection.multi_year_projections import (
                MultiYearProjectionEngine,
                generate_projection_timeline_data,
            )

            engine = MultiYearProjectionEngine()
            result = engine.project_multi_year(tax_return=tax_return, years=3)
            timeline = generate_projection_timeline_data(result)

            projections = []
            for year in result.yearly_projections:
                projections.append({
                    "year": year.year,
                    "projected_income": float(year.total_income),
                    "projected_tax": float(year.total_tax),
                    "taxable_income": float(year.taxable_income),
                    "retirement_balance_eoy": float(year.retirement_balance_eoy),
                    "cumulative_strategy_savings": float(year.cumulative_strategy_savings),
                    "assumptions": year.assumptions,
                    "strategy_notes": year.strategy_notes,
                })

            return {
                "current_year": {
                    "year": result.base_year,
                    "agi": tax_return.adjusted_gross_income or 0,
                    "tax": tax_return.tax_liability or 0,
                },
                "projection_years": result.projection_years,
                "projections": projections,
                "summary": timeline.get("summary", {}),
                "assumptions": result.assumptions,
            }
        except Exception as e:
            logger.error(f"Multi-year projection engine failed: {e}")

        current_tax = tax_return.tax_liability or 0
        agi = tax_return.adjusted_gross_income or 0
        return {
            "current_year": {"year": 2025, "agi": agi, "tax": current_tax},
            "projections": [],
            "assumptions": ["Multi-year engine unavailable; projection data could not be generated."],
            "planning_opportunities": [],
        }

    def _build_assumptions_appendix(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Build assumptions appendix (Premium)."""
        if self.computation_generator:
            try:
                statement = self.computation_generator(tax_return)
                full = statement.generate()
                return {
                    "assumptions": full.get("assumptions", []),
                    "data_sources": [
                        "User-provided income documents",
                        "IRS Publication 17",
                        "State tax authority guidelines",
                    ],
                }
            except Exception as e:
                logger.error(f"Assumptions appendix error: {e}")

        return {
            "assumptions": [],
            "data_sources": [],
        }

    def _build_irc_citations_appendix(self) -> Dict[str, Any]:
        """Build IRC citations appendix (Premium)."""
        return {
            "citations": [
                {"code": "IRC §1", "description": "Tax imposed on individuals"},
                {"code": "IRC §63", "description": "Standard deduction definition"},
                {"code": "IRC §151", "description": "Personal exemptions (suspended)"},
                {"code": "IRC §199A", "description": "Qualified business income deduction"},
                {"code": "IRC §401(k)", "description": "Qualified cash or deferred arrangements"},
                {"code": "IRC §408", "description": "Individual retirement accounts"},
                {"code": "IRC §223", "description": "Health savings accounts"},
                {"code": "IRC §1211", "description": "Capital loss limitations"},
                {"code": "IRC §170", "description": "Charitable contributions"},
            ],
            "publications": [
                "IRS Publication 17 - Your Federal Income Tax",
                "IRS Publication 334 - Tax Guide for Small Business",
                "IRS Publication 590 - Individual Retirement Arrangements",
            ],
        }

    def _build_calculations_appendix(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Build calculations appendix (Premium)."""
        if self.computation_generator:
            try:
                statement = self.computation_generator(tax_return)
                full = statement.generate()
                return {
                    "parts": full.get("parts", []),
                    "footnotes": full.get("footnotes", []),
                }
            except Exception as e:
                logger.error(f"Calculations appendix error: {e}")

        return {"parts": [], "footnotes": []}

    # =========================================================================
    # ACTION ITEM ENGINE
    # =========================================================================

    def _generate_action_items(
        self, tax_return: "TaxReturn", session_id: str
    ) -> List[ActionItem]:
        """
        Generate and prioritize action items.

        Priority levels:
        1 = Immediate (deadline-driven)
        2 = High (>$1000 potential savings)
        3 = Medium ($100-$1000 potential savings)
        4 = Low (<$100 or convenience)
        """
        if self.advisory_service:
            try:
                optimizer = self.advisory_service.optimizer_adapter
                if optimizer:
                    strategy = optimizer.get_full_strategy(session_id)
                    if strategy.success:
                        def _priority(value: Any) -> int:
                            if isinstance(value, int):
                                return max(1, min(4, value))
                            normalized = str(value or "").strip().lower()
                            mapping = {"critical": 1, "high": 2, "medium": 3, "low": 4}
                            return mapping.get(normalized, 3)

                        items: List[ActionItem] = []
                        pools = [
                            (strategy.data or {}).get("immediate_strategies", []),
                            (strategy.data or {}).get("current_year_strategies", []),
                            (strategy.data or {}).get("next_year_strategies", []),
                        ]
                        seen: set[str] = set()

                        for pool in pools:
                            for idx, rec in enumerate(pool):
                                title = str(rec.get("title") or "").strip()
                                if not title:
                                    continue
                                key = title.lower()
                                if key in seen:
                                    continue
                                seen.add(key)
                                items.append(
                                    ActionItem(
                                        action_id=f"strategy_{len(items)+1}",
                                        title=title,
                                        description=str(rec.get("description") or "Review this strategy with your CPA."),
                                        priority=_priority(rec.get("priority")),
                                        category="tax_savings",
                                        potential_savings=float(rec.get("estimated_savings") or 0.0),
                                        deadline=rec.get("deadline"),
                                    )
                                )

                        items.sort(key=lambda x: (x.priority, -x.potential_savings))
                        if items:
                            return items[:10]
            except Exception as e:
                logger.error(f"Action item strategy generation error: {e}")

        items: List[ActionItem] = []

        # Retirement contribution opportunities
        income = tax_return.income
        current_401k = self._estimate_401k_contribution(tax_return)
        if current_401k < 23500:
            room = 23500 - current_401k
            savings = room * 0.22  # Est. marginal rate
            items.append(ActionItem(
                action_id="401k_max",
                title="Maximize 401(k) Contribution",
                description=f"You have ${room:,.0f} of unused 401(k) space. Contributing more could save ~${savings:,.0f} in taxes.",
                priority=2 if savings > 1000 else 3,
                category="tax_savings",
                potential_savings=savings,
                deadline="December 31, 2025",
                irs_reference="IRC §401(k)",
            ))

        # IRA contribution
        current_ira = self._estimate_ira_contribution(tax_return)
        if current_ira < 7000:
            room = 7000 - current_ira
            savings = room * 0.22
            items.append(ActionItem(
                action_id="ira_contribute",
                title="Contribute to IRA",
                description=f"You can contribute up to ${room:,.0f} more to an IRA before April 15, 2026.",
                priority=2 if savings > 1000 else 3,
                category="tax_savings",
                potential_savings=savings,
                deadline="April 15, 2026",
                irs_reference="IRC §408",
            ))

        # HSA contribution
        current_hsa = self._estimate_hsa_contribution(tax_return)
        if current_hsa < 4300:
            room = 4300 - current_hsa
            savings = room * 0.22
            items.append(ActionItem(
                action_id="hsa_contribute",
                title="Maximize HSA Contribution",
                description=f"HSA contributions are triple tax-advantaged. You have ${room:,.0f} of room.",
                priority=2 if savings > 500 else 3,
                category="tax_savings",
                potential_savings=savings,
                deadline="April 15, 2026",
                irs_reference="IRC §223",
            ))

        # Estimated taxes
        refund_or_owed = tax_return.refund_or_owed or 0
        if refund_or_owed < -1000:
            items.append(ActionItem(
                action_id="estimated_taxes",
                title="Review Withholding or Estimated Taxes",
                description=f"You owe ${abs(refund_or_owed):,.0f}. Adjust W-4 or make estimated payments to avoid penalties.",
                priority=1,
                category="compliance",
                deadline="January 15, 2026 (Q4 estimated)",
            ))

        # Large refund
        if refund_or_owed > 3000:
            items.append(ActionItem(
                action_id="adjust_withholding",
                title="Reduce Excess Withholding",
                description=f"Your ${refund_or_owed:,.0f} refund means you're giving the IRS an interest-free loan. Adjust your W-4.",
                priority=4,
                category="planning",
            ))

        # Self-employment S-Corp
        se_income = getattr(income, 'self_employment_income', 0) or 0
        if se_income > 50000:
            se_tax = se_income * 0.9235 * 0.153
            items.append(ActionItem(
                action_id="scorp_election",
                title="Evaluate S-Corporation Election",
                description=f"With ${se_income:,.0f} in self-employment income, an S-Corp could save ~${se_tax * 0.3:,.0f} in SE tax.",
                priority=2,
                category="tax_savings",
                potential_savings=se_tax * 0.3,
                irs_reference="IRC §1362",
            ))

        # Sort by priority
        items.sort(key=lambda x: (x.priority, -x.potential_savings))

        return items

    # =========================================================================
    # RENDERERS
    # =========================================================================

    def _render_html(self, report: GeneratedReport) -> str:
        """Render report to HTML for client portal."""
        brand_name = report.metadata.get("brand_name", "Tax Advisory Platform")
        sections_html = []

        for section in report.sections:
            section_html = f"""
            <section id="{section.section_id.value}" class="report-section">
                <h2>{section.title}</h2>
                <div class="section-content">
                    {self._content_to_html(section.content)}
                </div>
            </section>
            """
            sections_html.append(section_html)

        # Action items (Premium)
        action_items_html = ""
        if report.action_items:
            items_list = "".join([
                f"""
                <div class="action-item priority-{item.priority}">
                    <h4>{item.title}</h4>
                    <p>{item.description}</p>
                    <div class="action-meta">
                        <span class="potential-savings">${item.potential_savings:,.0f} potential savings</span>
                        {f'<span class="deadline">Due: {item.deadline}</span>' if item.deadline else ''}
                    </div>
                </div>
                """
                for item in report.action_items
            ])
            action_items_html = f"""
            <section id="action-items" class="report-section">
                <h2>Prioritized Action Items</h2>
                <div class="action-items-list">
                    {items_list}
                </div>
            </section>
            """

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Tax Advisory Report - {report.taxpayer_name}</title>
            <style>
                :root {{
                    --primary: #1e3a5f;
                    --primary-dark: #152b47;
                    --success: #10b981;
                    --warning: #f59e0b;
                    --danger: #ef4444;
                }}
                body {{ font-family: system-ui, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 2rem; }}
                .report-header {{ text-align: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 2px solid var(--primary); }}
                .report-section {{ margin: 2rem 0; padding: 1.5rem; background: #f8fafc; border-radius: 8px; }}
                .report-section h2 {{ color: var(--primary-dark); margin-top: 0; }}
                .metric {{ display: inline-block; padding: 1rem; background: white; border-radius: 8px; margin: 0.5rem; text-align: center; }}
                .metric-value {{ font-size: 1.5rem; font-weight: bold; color: var(--primary); }}
                .metric-label {{ font-size: 0.875rem; color: #64748b; }}
                .action-item {{ padding: 1rem; margin: 0.5rem 0; background: white; border-radius: 8px; border-left: 4px solid var(--primary); }}
                .action-item.priority-1 {{ border-left-color: var(--danger); }}
                .action-item.priority-2 {{ border-left-color: var(--warning); }}
                .action-item h4 {{ margin: 0 0 0.5rem 0; }}
                .potential-savings {{ color: var(--success); font-weight: bold; }}
                .deadline {{ color: var(--danger); margin-left: 1rem; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
                th {{ background: var(--primary); color: white; }}
            </style>
        </head>
        <body>
            <header class="report-header">
                <h1>Tax Advisory Report</h1>
                <p><strong>{report.taxpayer_name}</strong> | Tax Year {report.tax_year}</p>
                <p>Report Tier: {report.tier.value.title()} | Generated: {report.generated_at[:10]}</p>
            </header>

            <main>
                {''.join(sections_html)}
                {action_items_html}
            </main>

            <footer style="margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; font-size: 0.875rem; color: #64748b;">
                <p>Report ID: {report.report_id} | {brand_name}</p>
            </footer>
        </body>
        </html>
        """

    def _content_to_html(self, content: Dict[str, Any]) -> str:
        """Convert section content to HTML."""
        if not content:
            return "<p>No data available</p>"

        html_parts = []

        for key, value in content.items():
            if isinstance(value, dict):
                # Nested object - render as definition list
                items = "".join([f"<dt>{k}</dt><dd>{v}</dd>" for k, v in value.items()])
                html_parts.append(f"<dl>{items}</dl>")
            elif isinstance(value, list):
                # List - render as ul
                if value and isinstance(value[0], dict):
                    # List of objects - render as table
                    if value:
                        headers = value[0].keys()
                        thead = "".join([f"<th>{h}</th>" for h in headers])
                        rows = "".join([
                            "<tr>" + "".join([f"<td>{item.get(h, '')}</td>" for h in headers]) + "</tr>"
                            for item in value
                        ])
                        html_parts.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{rows}</tbody></table>")
                else:
                    items = "".join([f"<li>{item}</li>" for item in value])
                    html_parts.append(f"<ul>{items}</ul>")
            elif isinstance(value, (int, float)):
                # Number - format as metric
                label = key.replace("_", " ").title()
                formatted = f"${value:,.2f}" if "amount" in key or "income" in key or "tax" in key or "savings" in key else f"{value:,.2f}"
                html_parts.append(f'<div class="metric"><div class="metric-value">{formatted}</div><div class="metric-label">{label}</div></div>')
            else:
                # String
                if key == "text":
                    html_parts.append(f"<p style='white-space: pre-wrap;'>{value}</p>")
                else:
                    html_parts.append(f"<p><strong>{key.replace('_', ' ').title()}:</strong> {value}</p>")

        return "".join(html_parts)

    def _render_pdf(self, report: GeneratedReport) -> bytes:
        """Render report to PDF bytes using ReportLab (with text fallback)."""
        brand_name = report.metadata.get("brand_name", "Tax Advisory Platform")
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
            from reportlab.lib.colors import HexColor
            import io

            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            navy = HexColor("#1e3a5f")

            # --- Cover Page ---
            c.setFillColor(navy)
            c.rect(0, height - 2.5*inch, width, 2.5*inch, fill=1)
            c.setFillColor(HexColor("#ffffff"))
            c.setFont("Helvetica-Bold", 28)
            c.drawCentredString(width/2, height - 1.2*inch, "Tax Advisory Report")
            c.setFont("Helvetica", 16)
            c.drawCentredString(width/2, height - 1.7*inch, report.tier.value.upper())

            c.setFillColor(HexColor("#333333"))
            c.setFont("Helvetica", 14)
            y = height - 3.2*inch
            c.drawString(1*inch, y, f"Prepared for: {report.taxpayer_name}")
            y -= 0.35*inch
            c.drawString(1*inch, y, f"Prepared by: {brand_name}")
            y -= 0.35*inch
            c.drawString(1*inch, y, f"Tax Year: {report.tax_year}")
            y -= 0.35*inch
            c.drawString(1*inch, y, f"Generated: {report.generated_at}")
            y -= 0.35*inch
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(1*inch, y, f"Report ID: {report.report_id}")

            c.setFont("Helvetica-Oblique", 9)
            c.setFillColor(HexColor("#666666"))
            c.drawCentredString(width/2, 0.75*inch, "Confidential - For intended recipient only")
            c.showPage()

            # --- Section Pages ---
            for section in report.sections:
                c.setFillColor(navy)
                c.rect(0, height - 0.8*inch, width, 0.8*inch, fill=1)
                c.setFillColor(HexColor("#ffffff"))
                c.setFont("Helvetica-Bold", 18)
                c.drawString(0.75*inch, height - 0.55*inch, section.title.upper())

                c.setFillColor(HexColor("#333333"))
                c.setFont("Helvetica", 11)
                y = height - 1.3*inch
                text_content = self._content_to_text(section.content)
                for line in text_content.split("\n"):
                    if y < 1*inch:
                        c.showPage()
                        y = height - 1*inch
                    c.drawString(0.75*inch, y, line[:90])  # Truncate long lines
                    y -= 0.2*inch
                c.showPage()

            # --- Action Items Page ---
            if report.action_items:
                c.setFillColor(navy)
                c.rect(0, height - 0.8*inch, width, 0.8*inch, fill=1)
                c.setFillColor(HexColor("#ffffff"))
                c.setFont("Helvetica-Bold", 18)
                c.drawString(0.75*inch, height - 0.55*inch, "PRIORITIZED ACTION ITEMS")

                c.setFillColor(HexColor("#333333"))
                y = height - 1.3*inch
                for i, item in enumerate(report.action_items, 1):
                    if y < 1.5*inch:
                        c.showPage()
                        y = height - 1*inch
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(0.75*inch, y, f"{i}. [{item.priority}] {item.title}")
                    y -= 0.25*inch
                    c.setFont("Helvetica", 10)
                    # Wrap description
                    desc = item.description[:120]
                    c.drawString(1*inch, y, desc)
                    y -= 0.2*inch
                    if item.potential_savings:
                        c.setFont("Helvetica-Bold", 10)
                        c.drawString(1*inch, y, f"Potential Savings: ${item.potential_savings:,.0f}")
                        y -= 0.2*inch
                    if item.deadline:
                        c.setFont("Helvetica-Oblique", 10)
                        c.drawString(1*inch, y, f"Deadline: {item.deadline}")
                        y -= 0.2*inch
                    y -= 0.15*inch  # Extra spacing between items
                c.showPage()

            # --- Disclaimer footer on last page ---
            c.setFont("Helvetica-Oblique", 8)
            c.setFillColor(HexColor("#999999"))
            c.drawCentredString(width/2, 0.5*inch,
                "This report is for informational purposes only. Consult a licensed tax professional for official filing.")
            c.showPage()

            c.save()
            buffer.seek(0)
            return buffer.read()

        except ImportError:
            # Fallback to text-based PDF representation
            lines = [
                "=" * 80,
                f"TAX ADVISORY REPORT - {report.tier.value.upper()}",
                "=" * 80,
                f"Taxpayer: {report.taxpayer_name}",
                f"Tax Year: {report.tax_year}",
                f"Generated: {report.generated_at}",
                f"Report ID: {report.report_id}",
                f"Prepared by: {brand_name}",
                "=" * 80,
                "",
            ]

            for section in report.sections:
                lines.append("-" * 60)
                lines.append(section.title.upper())
                lines.append("-" * 60)
                lines.append(self._content_to_text(section.content))
                lines.append("")

            if report.action_items:
                lines.append("=" * 60)
                lines.append("PRIORITIZED ACTION ITEMS")
                lines.append("=" * 60)
                for i, item in enumerate(report.action_items, 1):
                    lines.append(f"\n{i}. [{item.priority}] {item.title}")
                    lines.append(f"   {item.description}")
                    if item.potential_savings:
                        lines.append(f"   Potential Savings: ${item.potential_savings:,.0f}")
                    if item.deadline:
                        lines.append(f"   Deadline: {item.deadline}")

            return "\n".join(lines).encode('utf-8')

    def _content_to_text(self, content: Dict[str, Any]) -> str:
        """Convert content to plain text."""
        lines = []
        for key, value in content.items():
            if isinstance(value, dict):
                lines.append(f"  {key}:")
                for k, v in value.items():
                    lines.append(f"    {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"  {key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"    - {item}")
                    else:
                        lines.append(f"    - {item}")
            else:
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def _render_json(self, report: GeneratedReport) -> Dict[str, Any]:
        """Render report to JSON structure."""
        return {
            "report_id": report.report_id,
            "session_id": report.session_id,
            "tier": report.tier.value,
            "format": report.format.value,
            "generated_at": report.generated_at,
            "taxpayer_name": report.taxpayer_name,
            "tax_year": report.tax_year,
            "sections": [
                {
                    "section_id": s.section_id.value,
                    "title": s.title,
                    "content": s.content,
                }
                for s in report.sections
            ],
            "action_items": [item.to_dict() for item in report.action_items],
            "metadata": report.metadata,
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_tax_return(self, session_id: str) -> Optional["TaxReturn"]:
        """Get tax return for session."""
        if self.tax_return_adapter:
            try:
                if hasattr(self.tax_return_adapter, "get_optimizer_compatible_return"):
                    wrapped = self.tax_return_adapter.get_optimizer_compatible_return(session_id)
                    if wrapped:
                        return wrapped
                return self.tax_return_adapter.get_tax_return(session_id)
            except Exception as e:
                logger.error(f"Failed to get tax return: {e}")
        return None

    def _get_taxpayer_name(self, tax_return: "TaxReturn") -> str:
        """Extract taxpayer name."""
        if tax_return.taxpayer:
            first = getattr(tax_return.taxpayer, 'first_name', '') or ''
            last = getattr(tax_return.taxpayer, 'last_name', '') or ''
            return f"{first} {last}".strip() or "Taxpayer"
        return "Taxpayer"

    def _get_filing_status(self, tax_return: "TaxReturn") -> str:
        """Extract filing status."""
        if tax_return.taxpayer and tax_return.taxpayer.filing_status:
            fs = tax_return.taxpayer.filing_status
            return fs.value if hasattr(fs, 'value') else str(fs)
        return "unknown"

    def _estimate_401k_contribution(self, tax_return: "TaxReturn") -> float:
        """Estimate employee 401(k) contribution from available return fields."""
        income = getattr(tax_return, "income", None)
        if income is None:
            return 0.0

        direct = getattr(income, "retirement_contributions_401k", None)
        if direct is None:
            direct = getattr(income, "retirement_contributions", None)
        if direct is not None:
            try:
                return max(0.0, float(direct))
            except (TypeError, ValueError):
                pass

        total = 0.0
        for w2 in getattr(income, "w2_forms", []) or []:
            try:
                total += float(getattr(w2, "retirement_plan_contributions", 0) or 0)
            except (TypeError, ValueError):
                continue
        return max(0.0, total)

    def _estimate_ira_contribution(self, tax_return: "TaxReturn") -> float:
        """Estimate IRA contribution from deductions data."""
        deductions = getattr(tax_return, "deductions", None)
        if deductions is None:
            return 0.0
        try:
            return max(0.0, float(getattr(deductions, "ira_contributions", 0) or 0))
        except (TypeError, ValueError):
            return 0.0

    def _estimate_hsa_contribution(self, tax_return: "TaxReturn") -> float:
        """Estimate HSA contribution from deductions and employer W-2 data."""
        deductions = getattr(tax_return, "deductions", None)
        direct = 0.0
        try:
            direct = float(getattr(deductions, "hsa_contributions", 0) or 0)
        except (TypeError, ValueError):
            direct = 0.0

        income = getattr(tax_return, "income", None)
        employer_hsa = 0.0
        if income is not None and hasattr(income, "get_employer_hsa_contributions"):
            try:
                employer_hsa = float(income.get_employer_hsa_contributions() or 0)
            except Exception:
                employer_hsa = 0.0
        elif income is not None:
            for w2 in getattr(income, "w2_forms", []) or []:
                try:
                    employer_hsa += float(getattr(w2, "employer_hsa_contribution", 0) or 0)
                except (TypeError, ValueError):
                    continue

        return max(0.0, direct + employer_hsa)

    def _error_report(
        self,
        report_id: str,
        session_id: str,
        tier: ReportTier,
        format: ReportFormat,
        error: str,
    ) -> GeneratedReport:
        """Create error report."""
        return GeneratedReport(
            report_id=report_id,
            session_id=session_id,
            tier=tier,
            format=format,
            generated_at=datetime.utcnow().isoformat(),
            taxpayer_name="Error",
            tax_year=2025,
            sections=[],
            action_items=[],
            metadata={"error": error},
            html_content=f"<div class='error'>{error}</div>",
        )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_report(
    session_id: str,
    tier: str = "basic",
    format: str = "html",
    brand_context: Optional[Dict[str, Any]] = None,
) -> GeneratedReport:
    """
    Convenience function to generate a report.

    Args:
        session_id: Client session ID
        tier: "basic", "standard", or "premium"
        format: "html", "pdf", or "json"

    Returns:
        GeneratedReport
    """
    generator = PremiumReportGenerator()
    return generator.generate(
        session_id=session_id,
        tier=ReportTier(tier),
        format=ReportFormat(format),
        brand_context=brand_context,
    )


def get_tier_sections(tier: str) -> List[str]:
    """Get list of section IDs for a tier."""
    tier_enum = ReportTier(tier)
    return [s.value for s in TIER_SECTIONS[tier_enum]]


def get_tier_pricing() -> Dict[str, Dict[str, Any]]:
    """Get tier pricing information."""
    return {
        "basic": {
            "price": 0,
            "label": "Basic",
            "description": "Tax summary and computation",
            "section_count": len(TIER_SECTIONS[ReportTier.BASIC]),
        },
        "standard": {
            "price": 79,
            "label": "Standard Advisory",
            "description": "Full advisory with scenarios",
            "section_count": len(TIER_SECTIONS[ReportTier.STANDARD]),
        },
        "premium": {
            "price": 199,
            "label": "Premium Comprehensive",
            "description": "Complete analysis with action items and appendices",
            "section_count": len(TIER_SECTIONS[ReportTier.PREMIUM]),
        },
    }
