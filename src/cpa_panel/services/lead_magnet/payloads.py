"""
Lead magnet payload builders for personalization, deadlines, charts, and sharing.

Extracted from LeadMagnetService:
- _normalize_occupation_type()
- _occupation_display()
- _build_personalization_payload()
- _build_deadline_payload()
- _build_comparison_chart_payload()
- _build_strategy_waterfall_payload()
- _build_tax_calendar_payload()
- _build_share_payload()
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import date
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

from cpa_panel.services.lead_magnet_service import (
    TaxProfile,
    TaxComplexity,
    TaxInsight,
    FilingStatus,
    IncomeSource,
    STATE_DISPLAY_NAMES,
)
from cpa_panel.services.lead_magnet.generator import (
    normalize_state_code,
    filing_status_display,
    income_range_display,
)


def normalize_occupation_type(
    occupation_type: Optional[str],
    profile: Optional[TaxProfile] = None,
) -> str:
    """Normalize occupation type to a controlled taxonomy."""
    normalized = (occupation_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    allowed = {"w2", "self_employed", "business_owner", "investor", "mixed"}
    if normalized in allowed:
        return normalized

    if profile:
        sources = {s.value if hasattr(s, "value") else str(s) for s in profile.income_sources}
        if "self_employed" in sources or profile.has_business:
            return "business_owner"
        if "investments" in sources and len(sources) > 1:
            return "mixed"
        if "investments" in sources:
            return "investor"

    return "w2"


def occupation_display(profile: TaxProfile) -> str:
    """Human-readable occupation type label."""
    normalized = normalize_occupation_type(profile.occupation_type, profile)
    mapping = {
        "w2": "W-2 households",
        "self_employed": "self-employed households",
        "business_owner": "business-owner households",
        "investor": "investor households",
        "mixed": "mixed-income households",
    }
    return mapping.get(normalized, "W-2 households")


def build_personalization_payload(
    profile: Optional[TaxProfile],
    complexity: TaxComplexity,
    savings_low: float,
    savings_high: float,
) -> Dict[str, Any]:
    """Build taxpayer-facing personalization tokens used across funnel steps."""
    if not profile:
        return {
            "line": "Your answers suggest meaningful tax optimization opportunities.",
            "tokens": {},
        }

    state_code = normalize_state_code(profile.state_code)
    state_name = STATE_DISPLAY_NAMES.get(state_code, "your state")
    filing_label = filing_status_display(profile.filing_status)
    occupation_label = occupation_display(profile)
    income_label = income_range_display(profile.income_range)
    complexity_label = complexity.value.replace("_", " ").title()
    avg_savings = int(round((savings_low + savings_high) / 2)) if (savings_low or savings_high) else 0

    line = (
        f"For {filing_label} and {occupation_label} in {state_name} with {income_label} income, "
        f"profiles like yours commonly miss around ${avg_savings:,.0f} in savings."
    )

    return {
        "line": line,
        "tokens": {
            "occupation_type": normalize_occupation_type(profile.occupation_type, profile),
            "filing_status": profile.filing_status.value,
            "filing_status_label": filing_label,
            "occupation_type_label": occupation_label,
            "state_code": state_code,
            "state_name": state_name,
            "income_range_label": income_label,
            "complexity_label": complexity_label,
            "avg_missed_savings": avg_savings,
        },
    }


def build_deadline_payload() -> Dict[str, Any]:
    """
    Build deadline urgency context for tax-season-aware messaging.
    Uses the next April 15 filing deadline.
    """
    today = date.today()
    deadline = date(today.year, 4, 15)
    if today > deadline:
        deadline = date(today.year + 1, 4, 15)

    days_remaining = (deadline - today).days
    if days_remaining <= 30:
        urgency = "critical"
    elif days_remaining <= 75:
        urgency = "high"
    elif days_remaining <= 150:
        urgency = "moderate"
    else:
        urgency = "planning"

    if urgency == "critical":
        message = f"Tax deadline in {days_remaining} days. High-impact moves should be prioritized now."
    elif urgency == "high":
        message = f"{days_remaining} days until the tax deadline. There is still time to lock in savings."
    elif urgency == "moderate":
        message = f"{days_remaining} days to filing day. This is the best window for proactive planning."
    else:
        message = f"{days_remaining} days until the next filing deadline. Planning early increases tax control."

    return {
        "deadline_date": deadline.isoformat(),
        "deadline_display": deadline.strftime("%b %d, %Y"),
        "days_remaining": days_remaining,
        "urgency": urgency,
        "message": message,
    }


def build_comparison_chart_payload(
    savings_low: float,
    savings_high: float,
    score_overall: int,
) -> Dict[str, Any]:
    """Build chart payload for teaser/report comparison visualizations."""
    missed_mid = max(0, int(round((savings_low + savings_high) / 2)))
    current_path = max(1200, int(round(missed_mid * 2.2)))
    optimized_path = max(0, current_path - missed_mid)
    optimized_pct = int(round((optimized_path / current_path) * 100)) if current_path else 0

    return {
        "bars": [
            {"label": "Current Tax Path", "value": current_path},
            {"label": "Optimized Path", "value": optimized_path},
        ],
        "waterfall": [
            {"label": "Current Path", "value": current_path, "kind": "base"},
            {"label": "Missed Savings", "value": -missed_mid, "kind": "delta"},
            {"label": "Optimized Path", "value": optimized_path, "kind": "total"},
        ],
        "score_to_savings_ratio": round(missed_mid / max(score_overall, 1), 2),
        "optimized_vs_current_percent": optimized_pct,
    }


def build_strategy_waterfall_payload(
    insights: List[TaxInsight],
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build canonical strategy waterfall payload consumed by teaser/report templates.

    Contract:
    {
        "bars": [{"label", "value", "percent", "cumulative"}],
        "total_value": int,
        "currency": "USD"
    }
    """
    selected = insights[:limit] if isinstance(limit, int) and limit > 0 else insights
    impacts: List[Tuple[str, int]] = []
    for insight in selected:
        value = int(round((insight.savings_low + insight.savings_high) / 2))
        impacts.append((insight.title, max(0, value)))

    max_value = max((value for _, value in impacts), default=0)
    running_total = 0
    bars: List[Dict[str, Any]] = []
    for label, value in impacts:
        running_total += value
        percent = int(round((value / max_value) * 100)) if max_value > 0 else 0
        bars.append({
            "label": label,
            "value": value,
            "percent": percent,
            "cumulative": running_total,
        })

    return {
        "bars": bars,
        "total_value": running_total,
        "currency": "USD",
    }


def build_tax_calendar_payload(max_items: int = 5) -> List[Dict[str, Any]]:
    """
    Build dynamic taxpayer calendar events relative to current date.
    Never hardcodes year and always returns month/day display fields.
    """
    today = date.today()
    years = (today.year, today.year + 1)
    candidates: List[Tuple[date, str, str]] = []

    for year in years:
        candidates.extend([
            (
                date(year, 1, 15),
                "Q4 Estimated Tax Payment Due",
                "Fourth-quarter estimated payment deadline.",
            ),
            (
                date(year, 4, 15),
                "Federal Filing Deadline",
                "File return or extension; IRA/HSA contribution deadline.",
            ),
            (
                date(year, 6, 15),
                "Q2 Estimated Tax Payment Due",
                "Second-quarter estimated payment deadline.",
            ),
            (
                date(year, 9, 15),
                "Q3 Estimated Tax Payment Due",
                "Third-quarter estimated payment deadline.",
            ),
            (
                date(year, 10, 15),
                "Extension Filing Deadline",
                "Extended individual return due date.",
            ),
        ])

    upcoming = sorted(
        [entry for entry in candidates if entry[0] >= today],
        key=lambda entry: entry[0],
    )[:max_items]

    payload: List[Dict[str, Any]] = []
    for entry_date, title, description in upcoming:
        days_remaining = (entry_date - today).days
        if days_remaining <= 7:
            urgency = "critical"
        elif days_remaining <= 30:
            urgency = "high"
        elif days_remaining <= 60:
            urgency = "moderate"
        else:
            urgency = "low"
        payload.append({
            "date_iso": entry_date.isoformat(),
            "month": entry_date.strftime("%b"),
            "day": entry_date.strftime("%d"),
            "title": title,
            "description": description,
            "days_remaining": days_remaining,
            "urgency": urgency,
        })

    return payload


def build_share_payload(
    session_id: str,
    score_overall: int,
    score_band: str,
    state_code: str,
    cpa_slug: Optional[str] = None,
    estimated_savings: Optional[int] = None,
) -> Dict[str, Any]:
    """Build share text/url payload for organic funnel distribution."""
    share_text = (
        f"My Tax Health Score is {score_overall}/100 ({score_band}). "
        f"I found hidden tax opportunities in {state_code}. Check your score."
    )
    if cpa_slug:
        share_url = f"/lead-magnet/?cpa={cpa_slug}&share=1&score={score_overall}"
    else:
        share_url = f"/lead-magnet/?share=1&score={score_overall}"
    share_image_params = {
        "score": int(score_overall),
        "band": score_band,
    }
    if cpa_slug:
        share_image_params["cpa"] = cpa_slug
    if estimated_savings and estimated_savings > 0:
        share_image_params["savings"] = f"${estimated_savings:,.0f}"
    share_image_url = f"/lead-magnet/share-card.svg?{urlencode(share_image_params)}"
    return {
        "text": share_text,
        "url": share_url,
        "image_url": share_image_url,
    }
