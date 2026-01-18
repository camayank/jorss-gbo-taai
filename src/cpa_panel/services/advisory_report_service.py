"""
Advisory Report Service for CPA Panel

Generates comprehensive advisory reports combining all optimization
analyses, AI insights, and recommendations into professional deliverables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ReportSection(str, Enum):
    """Available report sections."""
    EXECUTIVE_SUMMARY = "executive_summary"
    TAX_OVERVIEW = "tax_overview"
    CREDIT_ANALYSIS = "credit_analysis"
    DEDUCTION_ANALYSIS = "deduction_analysis"
    FILING_STATUS = "filing_status"
    ENTITY_STRUCTURE = "entity_structure"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    SCENARIO_COMPARISON = "scenario_comparison"
    ACTION_ITEMS = "action_items"
    DISCLAIMER = "disclaimer"


@dataclass
class ReportSectionContent:
    """Content for a report section."""
    section_id: str
    title: str
    content: str
    data: Optional[Dict[str, Any]] = None
    charts: Optional[List[Dict[str, Any]]] = None


class AdvisoryReportService:
    """
    Service for generating comprehensive advisory reports.

    Combines output from all optimizers and analyzers into
    professional client-ready reports.
    """

    def __init__(self):
        """Initialize report service."""
        self._optimizer_adapter = None
        self._ai_adapter = None

    @property
    def optimizer_adapter(self):
        """Lazy load optimizer adapter."""
        if self._optimizer_adapter is None:
            from cpa_panel.adapters.optimizer_adapter import get_optimizer_adapter
            self._optimizer_adapter = get_optimizer_adapter()
        return self._optimizer_adapter

    @property
    def ai_adapter(self):
        """Lazy load AI adapter."""
        if self._ai_adapter is None:
            from cpa_panel.adapters.ai_advisory_adapter import get_ai_advisory_adapter
            self._ai_adapter = get_ai_advisory_adapter()
        return self._ai_adapter

    def get_tax_return(self, session_id: str):
        """Get tax return from session."""
        try:
            from cpa_panel.adapters import TaxReturnAdapter
            adapter = TaxReturnAdapter()
            return adapter.get_tax_return(session_id)
        except Exception as e:
            logger.error(f"Failed to get tax return for {session_id}: {e}")
            return None

    def generate_report(
        self,
        session_id: str,
        sections: Optional[List[str]] = None,
        include_scenarios: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive advisory report.

        Args:
            session_id: Client session ID
            sections: Optional list of specific sections to include
            include_scenarios: Whether to run scenario analysis

        Returns:
            Complete report structure ready for rendering
        """
        tax_return = self.get_tax_return(session_id)
        if not tax_return:
            return {
                "success": False,
                "error": f"Tax return not found for session {session_id}",
            }

        # Determine which sections to include
        all_sections = list(ReportSection)
        if sections:
            selected = [s for s in all_sections if s.value in sections]
        else:
            selected = all_sections

        try:
            report_sections = []

            # Client info
            client_name = "Client"
            if tax_return.taxpayer:
                first = tax_return.taxpayer.first_name or ""
                last = tax_return.taxpayer.last_name or ""
                client_name = f"{first} {last}".strip() or "Client"

            filing_status = tax_return.taxpayer.filing_status.value if tax_return.taxpayer and tax_return.taxpayer.filing_status else "unknown"

            # Generate each section
            if ReportSection.EXECUTIVE_SUMMARY in selected:
                section = self._generate_executive_summary(session_id, tax_return)
                if section:
                    report_sections.append(section)

            if ReportSection.TAX_OVERVIEW in selected:
                section = self._generate_tax_overview(tax_return)
                if section:
                    report_sections.append(section)

            if ReportSection.CREDIT_ANALYSIS in selected:
                section = self._generate_credit_section(session_id)
                if section:
                    report_sections.append(section)

            if ReportSection.DEDUCTION_ANALYSIS in selected:
                section = self._generate_deduction_section(session_id)
                if section:
                    report_sections.append(section)

            if ReportSection.FILING_STATUS in selected:
                section = self._generate_filing_status_section(session_id)
                if section:
                    report_sections.append(section)

            if ReportSection.ENTITY_STRUCTURE in selected:
                section = self._generate_entity_section(session_id)
                if section:
                    report_sections.append(section)

            if ReportSection.RETIREMENT in selected:
                section = self._generate_retirement_section(session_id)
                if section:
                    report_sections.append(section)

            if ReportSection.INVESTMENT in selected:
                section = self._generate_investment_section(session_id)
                if section:
                    report_sections.append(section)

            if include_scenarios and ReportSection.SCENARIO_COMPARISON in selected:
                section = self._generate_scenario_section(session_id)
                if section:
                    report_sections.append(section)

            if ReportSection.ACTION_ITEMS in selected:
                section = self._generate_action_items(session_id)
                if section:
                    report_sections.append(section)

            if ReportSection.DISCLAIMER in selected:
                section = self._generate_disclaimer()
                report_sections.append(section)

            # Calculate total savings across all analyses
            total_savings = self._calculate_total_savings(report_sections)

            return {
                "success": True,
                "session_id": session_id,
                "report": {
                    "title": f"Tax Advisory Report - {client_name}",
                    "client_name": client_name,
                    "filing_status": filing_status,
                    "tax_year": tax_return.tax_year if hasattr(tax_return, 'tax_year') else 2025,
                    "generated_at": datetime.utcnow().isoformat(),
                    "total_potential_savings": total_savings,
                    "sections": [
                        {
                            "section_id": s.section_id,
                            "title": s.title,
                            "content": s.content,
                            "data": s.data,
                            "charts": s.charts,
                        }
                        for s in report_sections
                    ],
                    "section_count": len(report_sections),
                },
            }

        except Exception as e:
            logger.error(f"Report generation failed for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_report_sections(self) -> Dict[str, Any]:
        """Get list of available report sections."""
        return {
            "success": True,
            "sections": [
                {
                    "section_id": s.value,
                    "name": s.value.replace("_", " ").title(),
                    "description": self._get_section_description(s),
                }
                for s in ReportSection
            ],
        }

    def _generate_executive_summary(self, session_id: str, tax_return) -> Optional[ReportSectionContent]:
        """Generate executive summary section."""
        try:
            # Get AI insights for summary
            ai_result = self.ai_adapter.get_ai_enhanced_insights(session_id)

            summary = ai_result.get("summary", {})
            total_savings = ai_result.get("total_potential_savings", 0)

            agi = tax_return.adjusted_gross_income or 0
            tax_liability = tax_return.tax_liability or 0
            refund = tax_return.refund_or_owed or 0

            content = f"""
## Executive Summary

{summary.get('executive_summary', f'Based on our comprehensive analysis, we have identified ${total_savings:,.0f} in potential tax savings opportunities.')}

### Key Takeaways
{chr(10).join('- ' + t for t in summary.get('key_takeaways', ['Review the detailed analysis below for specific opportunities.']))}

### Current Tax Position
- **Adjusted Gross Income:** ${agi:,.0f}
- **Tax Liability:** ${tax_liability:,.0f}
- **Refund/Owed:** {'Refund of $' + f'{abs(refund):,.0f}' if refund > 0 else 'Amount owed: $' + f'{abs(refund):,.0f}'}
- **Total Potential Savings:** ${total_savings:,.0f}
"""

            return ReportSectionContent(
                section_id=ReportSection.EXECUTIVE_SUMMARY.value,
                title="Executive Summary",
                content=content,
                data={
                    "agi": agi,
                    "tax_liability": tax_liability,
                    "refund_or_owed": refund,
                    "total_potential_savings": total_savings,
                },
            )

        except Exception as e:
            logger.warning(f"Executive summary generation failed: {e}")
            return None

    def _generate_tax_overview(self, tax_return) -> Optional[ReportSectionContent]:
        """Generate tax overview section."""
        try:
            agi = tax_return.adjusted_gross_income or 0
            taxable = tax_return.taxable_income or 0
            liability = tax_return.tax_liability or 0
            effective_rate = (liability / agi * 100) if agi > 0 else 0

            content = f"""
## Tax Overview

### Income Summary
- **Adjusted Gross Income:** ${agi:,.0f}
- **Taxable Income:** ${taxable:,.0f}
- **Total Tax Liability:** ${liability:,.0f}
- **Effective Tax Rate:** {effective_rate:.1f}%

### Income Sources
"""
            income = tax_return.income
            if income:
                wages = sum(w.wages for w in income.w2_forms) if hasattr(income, 'w2_forms') and income.w2_forms else 0
                if wages > 0:
                    content += f"- W-2 Wages: ${wages:,.0f}\n"
                se = getattr(income, 'self_employment_income', 0) or 0
                if se > 0:
                    content += f"- Self-Employment: ${se:,.0f}\n"
                interest = getattr(income, 'interest_income', 0) or 0
                if interest > 0:
                    content += f"- Interest: ${interest:,.0f}\n"
                dividends = getattr(income, 'ordinary_dividends', 0) or 0
                if dividends > 0:
                    content += f"- Dividends: ${dividends:,.0f}\n"

            return ReportSectionContent(
                section_id=ReportSection.TAX_OVERVIEW.value,
                title="Tax Overview",
                content=content,
                data={
                    "agi": agi,
                    "taxable_income": taxable,
                    "tax_liability": liability,
                    "effective_rate": effective_rate,
                },
            )

        except Exception as e:
            logger.warning(f"Tax overview generation failed: {e}")
            return None

    def _generate_credit_section(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate credit analysis section."""
        try:
            result = self.optimizer_adapter.get_credit_analysis(session_id)
            if not result.success:
                return None

            data = result.data
            content = f"""
## Tax Credit Analysis

### Summary
- **Total Potential Credits:** ${data.get('total_credits_claimed', 0):,.0f}
- **Refundable Credits:** ${data.get('total_refundable_credits', 0):,.0f}
- **Nonrefundable Credits:** ${data.get('total_nonrefundable_credits', 0):,.0f}
- **Unclaimed Potential:** ${data.get('unclaimed_potential', 0):,.0f}

### Eligible Credits
"""
            for code, credit in data.get('eligible_credits', {}).items():
                content += f"- **{credit['credit_name']}:** ${credit['actual_amount']:,.0f}\n"

            if data.get('near_miss_credits'):
                content += "\n### Near-Miss Opportunities\n"
                for credit in data.get('near_miss_credits', []):
                    content += f"- {credit}\n"

            return ReportSectionContent(
                section_id=ReportSection.CREDIT_ANALYSIS.value,
                title="Tax Credit Analysis",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.warning(f"Credit section generation failed: {e}")
            return None

    def _generate_deduction_section(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate deduction analysis section."""
        try:
            result = self.optimizer_adapter.get_deduction_analysis(session_id)
            if not result.success:
                return None

            data = result.data
            content = f"""
## Deduction Analysis

### Recommendation: {data.get('recommended_strategy', 'Standard').title()} Deduction

- **Standard Deduction:** ${data.get('total_standard_deduction', 0):,.0f}
- **Itemized Deductions:** ${data.get('total_itemized_deductions', 0):,.0f}
- **Tax Savings from Optimal Choice:** ${data.get('tax_savings_estimate', 0):,.0f}

### Itemized Breakdown
"""
            breakdown = data.get('itemized_breakdown', {})
            if breakdown.get('mortgage_interest', 0) > 0:
                content += f"- Mortgage Interest: ${breakdown.get('mortgage_interest', 0):,.0f}\n"
            if breakdown.get('salt_deduction_allowed', 0) > 0:
                content += f"- State and Local Taxes (SALT): ${breakdown.get('salt_deduction_allowed', 0):,.0f}\n"
            if breakdown.get('charitable_deduction_allowed', 0) > 0:
                content += f"- Charitable: ${breakdown.get('charitable_deduction_allowed', 0):,.0f}\n"
            if breakdown.get('medical_deduction_allowed', 0) > 0:
                content += f"- Medical (above floor): ${breakdown.get('medical_deduction_allowed', 0):,.0f}\n"

            return ReportSectionContent(
                section_id=ReportSection.DEDUCTION_ANALYSIS.value,
                title="Deduction Analysis",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.warning(f"Deduction section generation failed: {e}")
            return None

    def _generate_filing_status_section(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate filing status comparison section."""
        try:
            result = self.optimizer_adapter.get_filing_status_comparison(session_id)
            if not result.success:
                return None

            data = result.data
            content = f"""
## Filing Status Analysis

### Recommendation: {data.get('recommended_status', 'N/A').replace('_', ' ').title()}

{data.get('recommendation_reason', '')}

### Comparison
"""
            for status, analysis in data.get('analyses', {}).items():
                if analysis.get('is_eligible'):
                    content += f"\n**{status.replace('_', ' ').title()}**\n"
                    content += f"- Total Tax: ${analysis.get('total_tax', 0):,.0f}\n"
                    content += f"- Effective Rate: {analysis.get('effective_rate', 0):.1f}%\n"

            if data.get('potential_savings', 0) > 0:
                content += f"\n### Potential Savings: ${data.get('potential_savings', 0):,.0f}"

            return ReportSectionContent(
                section_id=ReportSection.FILING_STATUS.value,
                title="Filing Status Analysis",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.warning(f"Filing status section generation failed: {e}")
            return None

    def _generate_entity_section(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate entity structure section."""
        try:
            result = self.optimizer_adapter.get_entity_comparison(session_id)
            if not result.success or result.data.get("message"):
                return None  # Skip if no self-employment income

            data = result.data
            content = f"""
## Business Entity Analysis

### Recommendation: {data.get('recommended_entity', 'N/A').replace('_', ' ').title()}

{result.summary}

### Structure Comparison
"""
            for entity_type, analysis in data.get('analyses', {}).items():
                content += f"\n**{analysis.get('entity_name', entity_type)}**\n"
                content += f"- Total Business Tax: ${analysis.get('total_business_tax', 0):,.0f}\n"
                content += f"- Effective Rate: {analysis.get('effective_tax_rate', 0):.1f}%\n"
                content += f"- Annual Compliance Cost: ${analysis.get('annual_compliance_cost', 0):,.0f}\n"

            if data.get('max_annual_savings', 0) > 0:
                content += f"\n### Maximum Annual Savings: ${data.get('max_annual_savings', 0):,.0f}"
                content += f"\n### 5-Year Savings: ${data.get('five_year_savings', 0):,.0f}"

            return ReportSectionContent(
                section_id=ReportSection.ENTITY_STRUCTURE.value,
                title="Business Entity Analysis",
                content=content,
                data=data,
            )

        except Exception as e:
            logger.warning(f"Entity section generation failed: {e}")
            return None

    def _generate_retirement_section(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate retirement planning section."""
        try:
            result = self.optimizer_adapter.get_full_strategy(session_id)
            if not result.success:
                return None

            retirement = result.data.get('retirement_analysis', {})
            if not retirement:
                return None

            content = f"""
## Retirement Planning

### Current Contributions
- **401(k):** ${retirement.get('current_401k_contribution', 0):,.0f} / ${retirement.get('max_401k_contribution', 0):,.0f}
- **IRA:** ${retirement.get('current_ira_contribution', 0):,.0f} / ${retirement.get('max_ira_contribution', 0):,.0f}

### Optimization Opportunity
- **Additional Contribution Potential:** ${retirement.get('additional_contribution_potential', 0):,.0f}
- **Tax Savings if Maxed:** ${retirement.get('tax_savings_if_maxed', 0):,.0f}

### Recommendation
{retirement.get('roth_vs_traditional_recommendation', 'Consider your current vs. expected future tax rate when choosing between Traditional and Roth accounts.')}
"""

            return ReportSectionContent(
                section_id=ReportSection.RETIREMENT.value,
                title="Retirement Planning",
                content=content,
                data=retirement,
            )

        except Exception as e:
            logger.warning(f"Retirement section generation failed: {e}")
            return None

    def _generate_investment_section(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate investment strategy section."""
        try:
            result = self.optimizer_adapter.get_full_strategy(session_id)
            if not result.success:
                return None

            investment = result.data.get('investment_analysis', {})
            if not investment:
                return None

            content = f"""
## Investment Tax Strategy

### Current Position
- **Unrealized Gains:** ${investment.get('unrealized_gains', 0):,.0f}
- **Unrealized Losses:** ${investment.get('unrealized_losses', 0):,.0f}
- **Tax-Loss Harvesting Potential:** ${investment.get('tax_loss_harvesting_potential', 0):,.0f}

### Dividend Income
- **Qualified Dividends:** ${investment.get('qualified_dividend_amount', 0):,.0f}
- **NIIT Exposure:** ${investment.get('estimated_niit_exposure', 0):,.0f}

### Recommendations
"""
            for rec in investment.get('tax_efficient_placement_recommendations', []):
                content += f"- {rec}\n"

            return ReportSectionContent(
                section_id=ReportSection.INVESTMENT.value,
                title="Investment Tax Strategy",
                content=content,
                data=investment,
            )

        except Exception as e:
            logger.warning(f"Investment section generation failed: {e}")
            return None

    def _generate_scenario_section(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate scenario comparison section."""
        try:
            from cpa_panel.services.scenario_service import get_scenario_service
            service = get_scenario_service()

            # Get common scenarios
            common = service.get_common_scenarios(session_id)
            if not common.get("success"):
                return None

            scenarios = common.get("suggested_scenarios", [])
            if not scenarios:
                return None

            content = """
## What-If Scenario Analysis

### Potential Scenarios to Consider
"""
            for scenario in scenarios[:4]:
                content += f"\n**{scenario.get('name', 'Scenario')}**\n"
                content += f"{scenario.get('description', '')}\n"
                for adj in scenario.get('adjustments', []):
                    content += f"- {adj.get('description', adj.get('field'))}: ${adj.get('value', 0):,.0f}\n"

            content += "\n*Run scenario comparison for detailed tax impact analysis.*"

            return ReportSectionContent(
                section_id=ReportSection.SCENARIO_COMPARISON.value,
                title="What-If Analysis",
                content=content,
                data={"scenarios": scenarios},
            )

        except Exception as e:
            logger.warning(f"Scenario section generation failed: {e}")
            return None

    def _generate_action_items(self, session_id: str) -> Optional[ReportSectionContent]:
        """Generate action items section."""
        try:
            result = self.optimizer_adapter.get_full_strategy(session_id)
            if not result.success:
                return None

            content = """
## Recommended Action Items

### Immediate Actions
"""
            for strategy in result.data.get('immediate_strategies', [])[:5]:
                content += f"- **{strategy['title']}** (Est. Savings: ${strategy['estimated_savings']:,.0f})\n"
                content += f"  {strategy['description']}\n"

            content += "\n### Current Year Planning\n"
            for strategy in result.data.get('current_year_strategies', [])[:5]:
                content += f"- **{strategy['title']}** (Est. Savings: ${strategy['estimated_savings']:,.0f})\n"

            content += "\n### Next Year Planning\n"
            for strategy in result.data.get('next_year_strategies', [])[:3]:
                content += f"- **{strategy['title']}**\n"

            return ReportSectionContent(
                section_id=ReportSection.ACTION_ITEMS.value,
                title="Action Items",
                content=content,
                data={
                    "immediate": result.data.get('immediate_strategies', []),
                    "current_year": result.data.get('current_year_strategies', []),
                    "next_year": result.data.get('next_year_strategies', []),
                },
            )

        except Exception as e:
            logger.warning(f"Action items generation failed: {e}")
            return None

    def _generate_disclaimer(self) -> ReportSectionContent:
        """Generate disclaimer section."""
        content = """
## Important Disclaimer

This advisory report is provided for informational purposes only and does not constitute tax advice.
The analysis and recommendations contained herein are based on the information provided and current tax law.

**Please note:**
- Tax laws and regulations are subject to change
- Individual circumstances may vary
- Consult with your tax professional before making any tax-related decisions
- This platform provides advisory preparation support; it is NOT an e-filing service
- Final tax return preparation and filing is the responsibility of the CPA

*Generated by the Tax Advisory Platform. All calculations are estimates and should be verified.*
"""

        return ReportSectionContent(
            section_id=ReportSection.DISCLAIMER.value,
            title="Disclaimer",
            content=content,
        )

    def _calculate_total_savings(self, sections: List[ReportSectionContent]) -> float:
        """Calculate total potential savings across all sections."""
        total = 0
        for section in sections:
            if section.data:
                # Look for various savings fields
                total += section.data.get('total_potential_savings', 0)
                total += section.data.get('max_annual_savings', 0)
                total += section.data.get('tax_savings_estimate', 0)
                total += section.data.get('potential_savings', 0)
                total += section.data.get('tax_savings_if_maxed', 0)
                total += section.data.get('tax_loss_harvesting_potential', 0)
        return total

    def _get_section_description(self, section: ReportSection) -> str:
        """Get description for a report section."""
        descriptions = {
            ReportSection.EXECUTIVE_SUMMARY: "High-level overview and key takeaways",
            ReportSection.TAX_OVERVIEW: "Current tax position and income breakdown",
            ReportSection.CREDIT_ANALYSIS: "Tax credit eligibility and optimization",
            ReportSection.DEDUCTION_ANALYSIS: "Standard vs itemized deduction comparison",
            ReportSection.FILING_STATUS: "Filing status options and recommendations",
            ReportSection.ENTITY_STRUCTURE: "Business structure optimization (S-Corp, LLC)",
            ReportSection.RETIREMENT: "Retirement contribution strategies",
            ReportSection.INVESTMENT: "Investment tax planning",
            ReportSection.SCENARIO_COMPARISON: "What-if analysis scenarios",
            ReportSection.ACTION_ITEMS: "Prioritized recommendations and action items",
            ReportSection.DISCLAIMER: "Legal disclaimer and important notes",
        }
        return descriptions.get(section, "")


# Singleton instance
_report_service: Optional[AdvisoryReportService] = None


def get_report_service() -> AdvisoryReportService:
    """Get or create singleton report service."""
    global _report_service
    if _report_service is None:
        _report_service = AdvisoryReportService()
    return _report_service
