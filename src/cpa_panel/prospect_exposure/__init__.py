"""
Prospect Exposure Adapter

Provides a controlled intelligence layer for prospect-facing exposure.
This module transforms internal tax computation results into safe,
directional outputs that respect the 9 Red Lines.

RED LINES (Never expose to prospects):
1. Final/actionable tax positions
2. Filing-ready outputs/forms
3. Optimization logic/how-to mechanics
4. Risk conclusions/audit exposure judgments
5. AI-generated advisory language
6. Completeness/confidence signals
7. CPA internal review artifacts
8. Comparative CPA intelligence
9. Irreversibility/urgency framing
"""

from .contracts import (
    # Enums
    OutcomeType,
    AmountBand,
    ConfidenceBand,
    DisclaimerCode,
    ComplexityLevel,
    ComplexityReason,
    DriverCategory,
    DriverDirection,
    OpportunityCategory,
    OpportunitySeverity,
    ScenarioOutcomeShift,
    SummaryMessageCode,
    # Output Contracts
    ProspectOutcomeExposure,
    ProspectComplexityExposure,
    DriverItem,
    ProspectDriverExposure,
    OpportunityLabel,
    ProspectOpportunityExposure,
    ScenarioComparison,
    ProspectScenarioExposure,
    ProspectDiscoverySummary,
)

from .transformers import (
    OutcomeWrapper,
    ComplexityClassifier,
    DriverSanitizer,
    OpportunityLabeler,
    ScenarioDirection,
    ProspectExposureAssembler,
)

__all__ = [
    # Enums
    "OutcomeType",
    "AmountBand",
    "ConfidenceBand",
    "DisclaimerCode",
    "ComplexityLevel",
    "ComplexityReason",
    "DriverCategory",
    "DriverDirection",
    "OpportunityCategory",
    "OpportunitySeverity",
    "ScenarioOutcomeShift",
    "SummaryMessageCode",
    # Output Contracts
    "ProspectOutcomeExposure",
    "ProspectComplexityExposure",
    "DriverItem",
    "ProspectDriverExposure",
    "OpportunityLabel",
    "ProspectOpportunityExposure",
    "ScenarioComparison",
    "ProspectScenarioExposure",
    "ProspectDiscoverySummary",
    # Transformers
    "OutcomeWrapper",
    "ComplexityClassifier",
    "DriverSanitizer",
    "OpportunityLabeler",
    "ScenarioDirection",
    "ProspectExposureAssembler",
]
