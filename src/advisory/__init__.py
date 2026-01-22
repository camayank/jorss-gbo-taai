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

__all__ = [
    "AdvisoryReportGenerator",
    "AdvisoryReportResult",
    "AdvisoryReportSection",
    "ReportType",
    "generate_advisory_report",
]
