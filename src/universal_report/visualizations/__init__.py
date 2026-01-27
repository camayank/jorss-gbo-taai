"""
Visualization Components for Universal Report System

This module provides visual components for tax reports:
- Savings Gauge: Semi-circular meter showing potential savings
- Charts: Bar, pie, and comparison charts for tax data
- Summary Cards: Key metric display cards
"""

from universal_report.visualizations.savings_gauge import SavingsGauge
from universal_report.visualizations.charts import ReportCharts
from universal_report.visualizations.summary_cards import SummaryCards

__all__ = [
    'SavingsGauge',
    'ReportCharts',
    'SummaryCards',
]
