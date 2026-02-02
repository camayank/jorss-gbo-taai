"""
Advisory Report System - Orchestrates existing tax engines into comprehensive reports.

This module leverages all existing functionality:
- Tax Calculator
- Recommendation Engine (80+ tests)
- Entity Optimizer (48 tests)
- Multi-Year Projector

Main exports:
    AdvisoryReportGenerator: Main report generation class
    generate_advisory_report: Convenience function
    ReportType: Report type enum
"""

from .report_generator import (
    AdvisoryReportGenerator,
    AdvisoryReportResult,
    AdvisoryReportSection,
    ReportType,
    generate_advisory_report,
)
from .ai_narrative_generator import (
    AINarrativeGenerator,
    ClientProfile,
    CommunicationStyle,
    TaxSophistication,
    GeneratedNarrative,
    get_narrative_generator,
)
from .report_summarizer import (
    AIReportSummarizer,
    SummaryLevel,
    ReportSummary,
    MultiLevelSummaries,
    get_report_summarizer,
)

__all__ = [
    # Report generation
    "AdvisoryReportGenerator",
    "AdvisoryReportResult",
    "AdvisoryReportSection",
    "ReportType",
    "generate_advisory_report",
    # AI narrative generation
    "AINarrativeGenerator",
    "ClientProfile",
    "CommunicationStyle",
    "TaxSophistication",
    "GeneratedNarrative",
    "get_narrative_generator",
    # AI report summarization
    "AIReportSummarizer",
    "SummaryLevel",
    "ReportSummary",
    "MultiLevelSummaries",
    "get_report_summarizer",
]
