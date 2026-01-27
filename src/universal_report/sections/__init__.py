"""
Report Sections - Individual section components for reports.

This package contains individual section renderers that can be
used independently or combined via the SectionRenderer.

Available Sections:
- CoverPageRenderer: Professional cover page with branding
- ExecutiveSummaryRenderer: High-impact summary with key metrics
- TaxEducationRenderer: Educational content and strategy explanations
- RiskAssessmentRenderer: Audit risk indicators and compliance analysis
- TaxTimelineRenderer: Important tax deadlines and calendar
- DocumentChecklistRenderer: Required documents for tax filing
"""

from universal_report.sections.cover_page import CoverPageRenderer
from universal_report.sections.executive_summary import ExecutiveSummaryRenderer
from universal_report.sections.tax_education import TaxEducationRenderer
from universal_report.sections.risk_assessment import RiskAssessmentRenderer, AuditRiskFactor, RiskLevel
from universal_report.sections.tax_timeline import TaxTimelineRenderer, TaxDeadline, DeadlineType
from universal_report.sections.document_checklist import DocumentChecklistRenderer, DocumentItem


__all__ = [
    # Renderers
    'CoverPageRenderer',
    'ExecutiveSummaryRenderer',
    'TaxEducationRenderer',
    'RiskAssessmentRenderer',
    'TaxTimelineRenderer',
    'DocumentChecklistRenderer',
    # Data classes
    'AuditRiskFactor',
    'RiskLevel',
    'TaxDeadline',
    'DeadlineType',
    'DocumentItem',
]
