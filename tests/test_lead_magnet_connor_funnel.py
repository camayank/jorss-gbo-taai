from cpa_panel.services.lead_magnet_service import LeadMagnetService


def _high_opportunity_profile_payload() -> dict:
    return {
        "filing_status": "single",
        "state_code": "CA",
        "dependents_count": 1,
        "children_under_17": True,
        "income_range": "200k_500k",
        "income_sources": ["self_employed", "investments"],
        "is_homeowner": True,
        "retirement_savings": "none",
        "healthcare_type": "hdhp_hsa",
        "life_events": ["new_job", "business_start"],
        "has_student_loans": False,
        "has_business": True,
    }


def test_submit_tax_profile_returns_connor_payload_fields():
    service = LeadMagnetService()
    session = service.start_assessment()

    result = service.submit_tax_profile(
        session_id=session.session_id,
        filing_status="single",
        state_code="CA",
        dependents_count=1,
        has_children_under_17=True,
        income_range="200k_500k",
        income_sources=["self_employed", "investments"],
        is_homeowner=True,
        retirement_savings="none",
        healthcare_type="hdhp_hsa",
        life_events=["new_job", "business_start"],
        has_student_loans=False,
        has_business=True,
        privacy_consent=True,
    )

    assert "personalization_line" in result
    assert "score_benchmark" in result
    assert "comparison_chart" in result
    assert "deadline_context" in result
    assert "deadline_display" in result["deadline_context"]
    assert result["score_benchmark"]["average_taxpayer"] == 52
    assert result["score_benchmark"]["average_score"] == 52
    assert result["score_benchmark"]["cpa_planned_average"] == 78
    assert result["personalization_tokens"]["state_code"] == "CA"
    assert result["score_preview"] > 0


def test_tier_one_report_contains_score_subscores_and_share_payload():
    service = LeadMagnetService()
    session = service.start_assessment()
    service.submit_profile(session.session_id, _high_opportunity_profile_payload())

    report = service.get_tier_one_report(session.session_id)
    score = report["tax_health_score"]
    waterfall = report["strategy_waterfall"]

    assert "state_tax_efficiency" in score["subscores"]
    assert score["benchmark"]["cpa_optimized_target"] == 78
    assert score["benchmark"]["cpa_planned_average"] == 78
    assert report["personalization"]["tokens"]["state_code"] == "CA"
    assert len(report["comparison_chart"]["bars"]) == 2
    assert "share=1" in report["share_payload"]["url"]
    assert "share-card.svg" in report["share_payload"]["image_url"]
    assert report["locked_count"] >= 0
    assert report["teaser_insights"]
    assert waterfall["currency"] == "USD"
    assert waterfall["total_value"] >= 0
    assert isinstance(waterfall["bars"], list)
    if waterfall["bars"]:
        first = waterfall["bars"][0]
        assert {"label", "value", "percent", "cumulative"} <= set(first.keys())


def test_tier_two_report_calendar_is_dynamic_and_structured():
    service = LeadMagnetService()
    session = service.start_assessment()
    service.submit_profile(session.session_id, _high_opportunity_profile_payload())
    lead, _ = service.capture_contact(session.session_id, "Tester", "tester@example.com", "5555550100")
    service.mark_lead_engaged(lead.lead_id, engagement_letter_acknowledged=True)
    service.acknowledge_engagement_letter(lead.lead_id)

    report = service.get_tier_two_report(session.session_id)

    assert report["strategy_waterfall"]["bars"] is not None
    assert report["tax_calendar"], "Expected at least one upcoming tax calendar item"
    first = report["tax_calendar"][0]
    assert {"date_iso", "month", "day", "title", "description", "days_remaining", "urgency"} <= set(first.keys())
