"""
Tests for AnomalyDetector integration into CPA lead detail page.

Verifies:
1. Anomaly detection runs when tax computation data exists
2. anomaly_report is None when no session exists
3. anomaly_report is None when AnomalyDetector raises an exception
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.ai.anomaly_detector import (
    AnomalyDetector,
    AnomalyReport,
    Anomaly,
    AnomalyCategory,
    AnomalySeverity,
)


def _make_sample_report() -> AnomalyReport:
    """Create a sample AnomalyReport for testing."""
    return AnomalyReport(
        total_anomalies=2,
        critical_count=0,
        high_count=1,
        medium_count=1,
        low_count=0,
        anomalies=[
            Anomaly(
                category=AnomalyCategory.STATISTICAL,
                severity=AnomalySeverity.HIGH,
                field="charitable_deductions",
                description="Charitable deductions (18.0% of AGI) exceed audit threshold",
                current_value=18000,
                expected_range="1% - 10% of AGI",
                recommendation="Ensure documentation for all charitable contributions over $250",
                irs_reference="Publication 526",
                confidence=0.5,
            ),
            Anomaly(
                category=AnomalyCategory.AUDIT_TRIGGER,
                severity=AnomalySeverity.MEDIUM,
                field="high_income",
                description="High income (AGI > $500K) increases audit probability",
                current_value=None,
                confidence=0.8,
            ),
        ],
        overall_risk_score=45.5,
        audit_risk_level="medium",
        recommendations=[
            "Ensure documentation for all charitable contributions over $250",
            "High income (AGI > $500K) increases audit probability",
        ],
        raw_analysis="",
    )


async def _run_anomaly_detection(session_dict, session_id, tax_profile):
    """
    Extract of the anomaly detection logic from cpa_lead_detail().

    This mirrors the exact code added to the route handler, isolated
    so we can test it without needing to invoke the full FastAPI route.
    """
    anomaly_report = None
    if session_id and session_dict:
        try:
            from services.ai.anomaly_detector import AnomalyDetector
            tc = session_dict.get("tax_computation") or session_dict.get("data", {}).get("tax_computation")
            if tc:
                detector = AnomalyDetector()
                return_data = {
                    "filing_status": (tax_profile or {}).get("filing_status", "single"),
                    "income": tc.get("agi", 0),
                    "deductions": tc.get("total_deductions", 0),
                    "tax_liability": tc.get("total_tax", 0),
                    "dependents": (tax_profile or {}).get("dependents_count", 0),
                }
                anomaly_report = await detector.analyze_return(return_data)
        except Exception:
            pass
    return anomaly_report


@pytest.mark.asyncio
async def test_anomaly_report_returned_when_tax_computation_exists():
    """Anomaly report is returned when session has tax_computation data."""
    sample_report = _make_sample_report()

    session_dict = {
        "tax_computation": {
            "agi": 600000,
            "total_deductions": 50000,
            "total_tax": 150000,
        }
    }
    tax_profile = {"filing_status": "married_filing_jointly", "dependents_count": 2}

    with patch.object(AnomalyDetector, "analyze_return", new_callable=AsyncMock, return_value=sample_report):
        result = await _run_anomaly_detection(session_dict, "sess-123", tax_profile)

    assert result is not None
    assert result.total_anomalies == 2
    assert result.audit_risk_level == "medium"
    assert result.overall_risk_score == 45.5
    assert len(result.anomalies) == 2
    assert result.anomalies[0].severity == AnomalySeverity.HIGH
    assert result.anomalies[0].irs_reference == "Publication 526"


@pytest.mark.asyncio
async def test_anomaly_report_uses_nested_tax_computation():
    """Tax computation found under data.tax_computation is also used."""
    sample_report = _make_sample_report()

    session_dict = {
        "data": {
            "tax_computation": {
                "agi": 100000,
                "total_deductions": 15000,
                "total_tax": 20000,
            }
        }
    }

    with patch.object(AnomalyDetector, "analyze_return", new_callable=AsyncMock, return_value=sample_report) as mock_analyze:
        result = await _run_anomaly_detection(session_dict, "sess-456", None)

    assert result is not None
    mock_analyze.assert_awaited_once()
    call_args = mock_analyze.call_args[0][0]
    assert call_args["income"] == 100000
    assert call_args["filing_status"] == "single"  # default when tax_profile is None


@pytest.mark.asyncio
async def test_anomaly_report_none_when_no_session():
    """anomaly_report is None when session_id is missing."""
    result = await _run_anomaly_detection(None, None, None)
    assert result is None


@pytest.mark.asyncio
async def test_anomaly_report_none_when_no_tax_computation():
    """anomaly_report is None when session has no tax_computation."""
    session_dict = {"data": {"tax_profile": {"filing_status": "single"}}}
    result = await _run_anomaly_detection(session_dict, "sess-789", None)
    assert result is None


@pytest.mark.asyncio
async def test_anomaly_report_none_on_exception():
    """anomaly_report is None when AnomalyDetector raises an exception (graceful failure)."""
    session_dict = {
        "tax_computation": {
            "agi": 100000,
            "total_deductions": 10000,
            "total_tax": 20000,
        }
    }

    with patch.object(AnomalyDetector, "analyze_return", new_callable=AsyncMock, side_effect=RuntimeError("AI service unavailable")):
        result = await _run_anomaly_detection(session_dict, "sess-err", {"filing_status": "single"})

    assert result is None


@pytest.mark.asyncio
async def test_anomaly_report_fields_accessible():
    """Verify all AnomalyReport fields used by the template are accessible."""
    report = _make_sample_report()

    # These are the fields accessed in lead_detail.html
    assert isinstance(report.audit_risk_level, str)
    assert isinstance(report.overall_risk_score, float)
    assert isinstance(report.total_anomalies, int)
    assert isinstance(report.critical_count, int)
    assert isinstance(report.high_count, int)
    assert isinstance(report.anomalies, list)
    assert isinstance(report.recommendations, list)

    # Anomaly fields used in the template
    anomaly = report.anomalies[0]
    assert hasattr(anomaly.category, "value")
    assert hasattr(anomaly.severity, "value")
    assert isinstance(anomaly.description, str)
    assert anomaly.irs_reference is not None
    assert anomaly.recommendation is not None
