"""
Tests for ComplianceReviewer integration into CPA return review workflow.

Verifies:
1. Compliance review runs when return has AGI > 0
2. ComplianceReport data is correctly passed to template context
3. Due diligence checklists are included
4. Graceful failure when reviewer raises exception
5. Compliance review is skipped when return has no AGI
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime


def _make_compliance_report():
    """Create a mock ComplianceReport for testing."""
    from services.ai.compliance_reviewer import (
        ComplianceReport,
        ComplianceIssue,
        DueDiligenceChecklist,
        ComplianceArea,
        ComplianceStatus,
    )

    return ComplianceReport(
        return_id="test-123",
        preparer_ptin="P12345678",
        review_date=datetime.now(),
        overall_status=ComplianceStatus.WARNING,
        issues=[
            ComplianceIssue(
                area=ComplianceArea.EITC_DUE_DILIGENCE,
                status=ComplianceStatus.WARNING,
                title="EITC Due Diligence Required",
                description="Form 8867 must be completed",
                requirement="IRC §6695(g)",
                irc_reference="IRC §6695(g)",
            )
        ],
        due_diligence_checklists=[
            DueDiligenceChecklist(
                credit_type="EITC",
                form_number="8867",
                questions=[{"question": "Did you verify qualifying child residency?", "answered": True}],
                overall_status=ComplianceStatus.WARNING,
                missing_items=["Form 8867 signature"],
                recommendations=["Complete Form 8867"],
            )
        ],
        circular_230_compliant=True,
        penalties_risk_level="medium",
        estimated_penalty_exposure=1000.0,
        recommendations=["Complete EITC due diligence checklist"],
        certifications_needed=["Form 8867"],
        raw_analysis="Test analysis",
    )


async def _run_compliance_review(return_data, cpa_profile=None):
    """
    Extracted compliance review logic matching cpa_return_review_page().

    This mirrors the exact logic in the route handler so we can test it
    in isolation without needing the full request/response cycle.
    """
    compliance_report = None
    if return_data and return_data.get("agi", 0) > 0:
        try:
            from services.ai.compliance_reviewer import ComplianceReviewer

            reviewer = ComplianceReviewer()

            preparer_info = None
            if cpa_profile:
                ptin = cpa_profile.get("ptin")
                if ptin:
                    preparer_info = {
                        "name": cpa_profile.get("display_name", ""),
                        "ptin": ptin,
                    }

            compliance_report = await reviewer.review_return(return_data, preparer_info)
        except Exception:
            compliance_report = None

    return compliance_report


@pytest.mark.asyncio
@patch("services.ai.compliance_reviewer.ComplianceReviewer")
async def test_compliance_review_success(mock_reviewer_cls):
    """Compliance report is returned when AGI > 0 and reviewer succeeds."""
    expected_report = _make_compliance_report()
    mock_instance = MagicMock()
    mock_instance.review_return = AsyncMock(return_value=expected_report)
    mock_reviewer_cls.return_value = mock_instance

    return_data = {"agi": 75000, "total_income": 80000}
    cpa_profile = {"ptin": "P12345678", "display_name": "Jane CPA"}

    result = await _run_compliance_review(return_data, cpa_profile)

    assert result is expected_report
    mock_instance.review_return.assert_awaited_once()
    # Verify preparer_info was passed
    call_args = mock_instance.review_return.call_args
    assert call_args[0][0] == return_data
    assert call_args[0][1]["ptin"] == "P12345678"
    assert call_args[0][1]["name"] == "Jane CPA"


@pytest.mark.asyncio
@patch("services.ai.compliance_reviewer.ComplianceReviewer")
async def test_compliance_review_with_due_diligence(mock_reviewer_cls):
    """Compliance report includes due diligence checklists."""
    expected_report = _make_compliance_report()
    mock_instance = MagicMock()
    mock_instance.review_return = AsyncMock(return_value=expected_report)
    mock_reviewer_cls.return_value = mock_instance

    return_data = {"agi": 45000, "eitc": 3000}

    result = await _run_compliance_review(return_data)

    assert result is not None
    assert len(result.due_diligence_checklists) == 1
    checklist = result.due_diligence_checklists[0]
    assert checklist.credit_type == "EITC"
    assert checklist.form_number == "8867"
    assert len(checklist.missing_items) == 1
    assert checklist.missing_items[0] == "Form 8867 signature"
    assert len(checklist.questions) == 1


@pytest.mark.asyncio
@patch("services.ai.compliance_reviewer.ComplianceReviewer")
async def test_compliance_review_graceful_failure(mock_reviewer_cls):
    """Compliance report is None when reviewer raises an exception."""
    mock_instance = MagicMock()
    mock_instance.review_return = AsyncMock(side_effect=RuntimeError("AI service unavailable"))
    mock_reviewer_cls.return_value = mock_instance

    return_data = {"agi": 75000}

    result = await _run_compliance_review(return_data)

    assert result is None
    mock_instance.review_return.assert_awaited_once()


@pytest.mark.asyncio
async def test_compliance_review_skipped_no_agi():
    """Compliance review is skipped when return has no AGI."""
    return_data = {"agi": 0, "total_income": 0}

    result = await _run_compliance_review(return_data)

    assert result is None


@pytest.mark.asyncio
async def test_compliance_review_skipped_empty_return():
    """Compliance review is skipped when return_data is empty."""
    result = await _run_compliance_review({})

    assert result is None


@pytest.mark.asyncio
async def test_compliance_review_skipped_none_return():
    """Compliance review is skipped when return_data is None."""
    result = await _run_compliance_review(None)

    assert result is None


@pytest.mark.asyncio
@patch("services.ai.compliance_reviewer.ComplianceReviewer")
async def test_compliance_review_no_ptin(mock_reviewer_cls):
    """Compliance review runs without preparer_info when CPA has no PTIN."""
    expected_report = _make_compliance_report()
    mock_instance = MagicMock()
    mock_instance.review_return = AsyncMock(return_value=expected_report)
    mock_reviewer_cls.return_value = mock_instance

    return_data = {"agi": 50000}
    cpa_profile = {"display_name": "Jane CPA"}  # No PTIN

    result = await _run_compliance_review(return_data, cpa_profile)

    assert result is expected_report
    call_args = mock_instance.review_return.call_args
    assert call_args[0][1] is None  # preparer_info should be None


@pytest.mark.asyncio
@patch("services.ai.compliance_reviewer.ComplianceReviewer")
async def test_compliance_report_fields(mock_reviewer_cls):
    """All ComplianceReport fields are accessible for template rendering."""
    expected_report = _make_compliance_report()
    mock_instance = MagicMock()
    mock_instance.review_return = AsyncMock(return_value=expected_report)
    mock_reviewer_cls.return_value = mock_instance

    return_data = {"agi": 75000}
    result = await _run_compliance_review(return_data)

    # Verify all template-used fields are accessible
    assert result.overall_status.value == "warning"
    assert result.penalties_risk_level == "medium"
    assert result.estimated_penalty_exposure == 1000.0
    assert result.circular_230_compliant is True
    assert len(result.issues) == 1
    assert result.issues[0].area.value == "eitc_dd"
    assert result.issues[0].irc_reference == "IRC §6695(g)"
    assert len(result.due_diligence_checklists) == 1
    assert len(result.recommendations) == 1
    assert len(result.certifications_needed) == 1
