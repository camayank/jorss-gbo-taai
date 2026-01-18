"""
CPA Analysis Module

Provides analytical tools for CPAs and clients:
- Delta analysis (before/after impact visualization)
- Tax drivers breakdown (what affects taxes most)
- Scenario comparison (what-if analysis)
"""

from .delta_analyzer import (
    DeltaAnalyzer,
    DeltaResult,
    ChangeType,
)
from .tax_drivers import (
    TaxDriversAnalyzer,
    TaxDriver,
    DriverDirection,
)
from .scenario_comparison import (
    ScenarioComparator,
    Scenario,
    ScenarioResult,
)

__all__ = [
    "DeltaAnalyzer",
    "DeltaResult",
    "ChangeType",
    "TaxDriversAnalyzer",
    "TaxDriver",
    "DriverDirection",
    "ScenarioComparator",
    "Scenario",
    "ScenarioResult",
]
