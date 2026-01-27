"""
Universal Dynamic Report Template System

A unified report generation system that dynamically renders reports based on
available data from any source (chatbot, manual entry, OCR, AI analysis, scenarios)
with professional visualizations.

Key Features:
- Charts/Graphs: Visual representation of tax data, comparisons, scenarios
- Logo/Branding Customization: White-label support for CPA firms
- Visual Savings Gauge/Meter: Dynamic visual indicator of potential savings
"""

# Use lazy imports to avoid circular dependencies
def __getattr__(name):
    """Lazy import for module attributes."""
    if name == 'UniversalReportEngine':
        from universal_report.template_engine import UniversalReportEngine
        return UniversalReportEngine
    elif name == 'ReportOutput':
        from universal_report.template_engine import ReportOutput
        return ReportOutput
    elif name in ('NormalizedReportData', 'ReportDataCollector', 'IncomeItem',
                  'DeductionItem', 'CreditItem', 'Recommendation', 'RiskFactor',
                  'Opportunity', 'Scenario', 'SourceType', 'PriorityLevel'):
        from universal_report import data_collector
        return getattr(data_collector, name)
    elif name in ('SectionRenderer', 'RenderedSection'):
        from universal_report import section_renderer
        return getattr(section_renderer, name)
    elif name in ('BrandTheme', 'ThemeManager'):
        from universal_report.branding import theme_manager
        return getattr(theme_manager, name)
    raise AttributeError(f"module 'universal_report' has no attribute '{name}'")


__all__ = [
    # Main engine
    'UniversalReportEngine',
    'ReportOutput',
    # Data structures
    'NormalizedReportData',
    'ReportDataCollector',
    'IncomeItem',
    'DeductionItem',
    'CreditItem',
    'Recommendation',
    'RiskFactor',
    'Opportunity',
    'Scenario',
    'SourceType',
    'PriorityLevel',
    # Rendering
    'SectionRenderer',
    'RenderedSection',
    # Branding
    'BrandTheme',
    'ThemeManager',
]
