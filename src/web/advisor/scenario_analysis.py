"""
Scenario analysis endpoints extracted from intelligent_advisor_api.py.

Contains:
- POST /roth-analysis
- POST /entity-analysis
- POST /deduction-analysis
- POST /amt-analysis
- GET  /audit-risk/{session_id}
"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from security.session_token import verify_session_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Scenario Analysis"])

# Lazy imports to avoid circular dependencies
_engine = None
_flags = None


def _get_engine():
    global _engine
    if _engine is None:
        from web.intelligent_advisor_api import chat_engine
        _engine = chat_engine
    return _engine


def _get_flags():
    global _flags
    if _flags is None:
        from web.intelligent_advisor_api import AI_CHAT_ENABLED, STANDARD_DISCLAIMER
        _flags = {"AI_CHAT_ENABLED": AI_CHAT_ENABLED, "STANDARD_DISCLAIMER": STANDARD_DISCLAIMER}
    return _flags


def _get_models():
    from web.advisor.models import FullAnalysisRequest
    return FullAnalysisRequest


@router.post("/roth-analysis")
async def analyze_roth_conversion(request=None, _session: str = Depends(verify_session_token)):
    """AI-powered Roth conversion analysis."""
    from web.intelligent_advisor_api import (
        chat_engine, AI_CHAT_ENABLED, STANDARD_DISCLAIMER, FullAnalysisRequest,
    )
    from calculator.decimal_math import money

    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)

        if AI_CHAT_ENABLED:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()
                result = await reasoning.analyze_roth_conversion(
                    traditional_balance=profile.get("traditional_ira_balance", 0) or 50000,
                    current_bracket=calculation.marginal_rate / 100,
                    projected_retirement_bracket=max(calculation.marginal_rate - 5, 10) / 100,
                    current_age=profile.get("age", 40) or 40,
                    years_to_retirement=max(65 - (profile.get("age", 40) or 40), 5),
                    filing_status=profile.get("filing_status", "single"),
                    social_security=profile.get("social_security", 0) or 0,
                    other_retirement_income=profile.get("retirement_income", 0) or 0,
                    state=profile.get("state", "CA"),
                )
                return {
                    "session_id": request.session_id,
                    "analysis": result.analysis[:1500],
                    "recommendation": result.recommendation,
                    "key_factors": result.key_factors,
                    "action_items": result.action_items[:5],
                    "risks": result.risks,
                    "confidence": result.confidence,
                    "irc_references": result.irc_references,
                    "requires_professional_review": result.requires_professional_review,
                    "disclaimer": STANDARD_DISCLAIMER,
                }
            except Exception as e:
                logger.warning(f"AI Roth analysis failed, using fallback: {e}")

        # Fallback
        current_tax = calculation.total_tax
        return {
            "session_id": request.session_id,
            "analysis": "Basic Roth conversion comparison based on current vs projected bracket.",
            "recommendation": "Convert if projected retirement bracket is lower than current bracket."
                if calculation.marginal_rate > 22 else "Consider keeping traditional if bracket is low.",
            "key_factors": [
                f"Current marginal rate: {calculation.marginal_rate}%",
                f"Current total tax: ${current_tax:,.0f}",
            ],
            "action_items": ["Consult with a CPA for personalized Roth conversion strategy"],
            "confidence": 0.5,
            "disclaimer": STANDARD_DISCLAIMER,
        }
    except Exception as e:
        logger.error(f"Roth analysis error: {e}")
        raise HTTPException(status_code=500, detail="Unable to complete Roth analysis.")


@router.post("/entity-analysis")
async def analyze_entity_structure(request=None, _session: str = Depends(verify_session_token)):
    """AI-powered business entity structure analysis."""
    from web.intelligent_advisor_api import (
        chat_engine, AI_CHAT_ENABLED, STANDARD_DISCLAIMER,
    )

    try:
        profile = request.profile.dict(exclude_none=True)
        business_income = profile.get("business_income", 0) or 0

        if AI_CHAT_ENABLED and business_income > 0:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()
                result = await reasoning.analyze_entity_structure(
                    gross_revenue=business_income,
                    business_expenses=profile.get("business_expenses", 0) or business_income * 0.3,
                    owner_salary=business_income * 0.6,
                    state=profile.get("state", "CA"),
                    filing_status=profile.get("filing_status", "single"),
                    other_income=(profile.get("total_income", 0) or 0) - business_income,
                    current_entity="sole_prop",
                )
                return {
                    "session_id": request.session_id,
                    "analysis": result.analysis[:1500],
                    "recommendation": result.recommendation,
                    "key_factors": result.key_factors,
                    "action_items": result.action_items[:5],
                    "risks": result.risks,
                    "confidence": result.confidence,
                    "irc_references": result.irc_references,
                    "requires_professional_review": result.requires_professional_review,
                    "disclaimer": STANDARD_DISCLAIMER,
                }
            except Exception as e:
                logger.warning(f"AI entity analysis failed, using fallback: {e}")

        # Fallback
        calculation = await chat_engine.get_tax_calculation(profile)
        se_tax = calculation.self_employment_tax if hasattr(calculation, 'self_employment_tax') else 0
        return {
            "session_id": request.session_id,
            "analysis": "Basic entity comparison: Sole Prop vs S-Corp.",
            "recommendation": "S-Corp recommended" if business_income > 50000 else "Sole proprietorship sufficient",
            "key_factors": [
                f"Business income: ${business_income:,.0f}",
                f"Potential SE tax savings: ${business_income * 0.5 * 0.153:,.0f}",
            ],
            "action_items": ["Consult with a CPA for entity structure optimization"],
            "confidence": 0.5,
            "disclaimer": STANDARD_DISCLAIMER,
        }
    except Exception as e:
        logger.error(f"Entity analysis error: {e}")
        raise HTTPException(status_code=500, detail="Unable to complete entity analysis.")


@router.post("/deduction-analysis")
async def analyze_deduction_strategy(request=None, _session: str = Depends(verify_session_token)):
    """AI-powered deduction optimization analysis."""
    from web.intelligent_advisor_api import (
        chat_engine, AI_CHAT_ENABLED, STANDARD_DISCLAIMER,
    )

    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)

        if AI_CHAT_ENABLED:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()
                current_deductions = {
                    "mortgage_interest": profile.get("mortgage_interest", 0) or 0,
                    "property_taxes": profile.get("property_taxes", 0) or 0,
                    "state_income_tax": profile.get("state_income_tax", 0) or 0,
                    "charitable_donations": profile.get("charitable_donations", 0) or 0,
                    "medical_expenses": profile.get("medical_expenses", 0) or 0,
                }
                potential_deductions = {
                    "retirement_401k": min(23500 - (profile.get("retirement_401k", 0) or 0), 23500),
                    "hsa": min(4300 - (profile.get("hsa_contributions", 0) or 0), 4300),
                    "ira": min(7000 - (profile.get("retirement_ira", 0) or 0), 7000),
                    "charitable_bunching": (profile.get("charitable_donations", 0) or 0) * 2,
                }
                result = await reasoning.analyze_deduction_strategy(
                    income=profile.get("total_income", 0) or 0,
                    current_deductions=current_deductions,
                    potential_deductions=potential_deductions,
                    filing_status=profile.get("filing_status", "single"),
                    state=profile.get("state", "CA"),
                )
                return {
                    "session_id": request.session_id,
                    "analysis": result.analysis[:1500],
                    "recommendation": result.recommendation,
                    "key_factors": result.key_factors,
                    "action_items": result.action_items[:5],
                    "risks": result.risks,
                    "confidence": result.confidence,
                    "irc_references": result.irc_references,
                    "requires_professional_review": result.requires_professional_review,
                    "disclaimer": STANDARD_DISCLAIMER,
                }
            except Exception as e:
                logger.warning(f"AI deduction analysis failed, using fallback: {e}")

        # Fallback
        itemized_est = (
            (profile.get("mortgage_interest", 0) or 0)
            + (profile.get("property_taxes", 0) or 0)
            + min((profile.get("state_income_tax", 0) or 0), 10000)
            + (profile.get("charitable_donations", 0) or 0)
        )
        return {
            "session_id": request.session_id,
            "analysis": f"Standard deduction: ${calculation.deductions:,.0f} vs Itemized estimate: ${itemized_est:,.0f}.",
            "recommendation": "Itemize" if itemized_est > calculation.deductions else "Take standard deduction",
            "key_factors": [
                f"Standard deduction: ${calculation.deductions:,.0f}",
                f"Itemized estimate: ${itemized_est:,.0f}",
            ],
            "action_items": ["Review all potential deductions with a tax professional"],
            "confidence": 0.6,
            "disclaimer": STANDARD_DISCLAIMER,
        }
    except Exception as e:
        logger.error(f"Deduction analysis error: {e}")
        raise HTTPException(status_code=500, detail="Unable to complete deduction analysis.")


@router.get("/audit-risk/{session_id}")
async def get_audit_risk(session_id: str, _session: str = Depends(verify_session_token)):
    """Dedicated audit risk assessment endpoint."""
    from web.intelligent_advisor_api import chat_engine, AI_CHAT_ENABLED, _profile_to_return_data

    try:
        session = await chat_engine.get_or_create_session(session_id)
        profile = session.get("profile", {})

        if not profile:
            raise HTTPException(status_code=404, detail="No profile data for this session.")

        if AI_CHAT_ENABLED:
            try:
                from services.ai.anomaly_detector import get_anomaly_detector
                detector = get_anomaly_detector()
                return_data = _profile_to_return_data(profile, session_id)
                assessment = await detector.assess_audit_risk(return_data)
                return {
                    "session_id": session_id,
                    "overall_risk": assessment.overall_risk,
                    "risk_score": assessment.risk_score,
                    "primary_triggers": assessment.primary_triggers,
                    "contributing_factors": assessment.contributing_factors,
                    "mitigating_factors": assessment.mitigating_factors,
                    "recommendations": assessment.recommendations,
                    "comparable_audit_rate": assessment.comparable_audit_rate,
                }
            except Exception as e:
                logger.warning(f"AI audit risk assessment failed: {e}")

        # Fallback: rule-based risk estimation
        income = profile.get("total_income", 0) or 0
        business_income = profile.get("business_income", 0) or 0
        risk = "low"
        score = 15
        triggers = []
        if income > 200000:
            risk = "medium"
            score = 40
            triggers.append("High income (>$200k)")
        if business_income > 0 and business_income > income * 0.5:
            score += 15
            triggers.append("Significant business income")
        if profile.get("charitable_donations", 0) and profile["charitable_donations"] > income * 0.3:
            score += 10
            triggers.append("High charitable deductions relative to income")
        if score >= 50:
            risk = "high"
        elif score >= 30:
            risk = "medium"

        return {
            "session_id": session_id,
            "overall_risk": risk,
            "risk_score": score,
            "primary_triggers": triggers,
            "contributing_factors": [],
            "mitigating_factors": [],
            "recommendations": ["Maintain thorough documentation for all deductions"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audit risk error: {e}")
        raise HTTPException(status_code=500, detail="Unable to assess audit risk.")


@router.post("/amt-analysis")
async def analyze_amt_exposure(request=None, _session: str = Depends(verify_session_token)):
    """AI-powered Alternative Minimum Tax exposure analysis."""
    from web.intelligent_advisor_api import chat_engine, AI_CHAT_ENABLED

    try:
        profile = request.profile.dict(exclude_none=True)

        if AI_CHAT_ENABLED:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()
                result = await reasoning.analyze_amt_exposure(
                    regular_income=profile.get("total_income", 0) or 0,
                    salt_deduction=min(
                        (profile.get("state_income_tax", 0) or 0) + (profile.get("property_taxes", 0) or 0),
                        10000
                    ),
                    misc_deductions=(profile.get("medical_expenses", 0) or 0),
                    iso_spread=0,
                    tax_exempt_interest=0,
                    filing_status=profile.get("filing_status", "single"),
                    dependents=profile.get("dependents", 0) or 0,
                    state=profile.get("state", "CA"),
                )
                return {
                    "session_id": request.session_id,
                    "analysis": result.analysis[:1500],
                    "recommendation": result.recommendation,
                    "key_factors": result.key_factors,
                    "action_items": result.action_items[:5],
                    "confidence": result.confidence,
                    "ai_powered": True,
                }
            except Exception as e:
                logger.warning(f"AI AMT analysis failed: {e}")

        # Fallback
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        exemption = 85700 if filing_status == "single" else 133300
        salt = min((profile.get("state_income_tax", 0) or 0) + (profile.get("property_taxes", 0) or 0), 10000)
        amt_income = income + salt
        amt_liable = amt_income > exemption

        return {
            "session_id": request.session_id,
            "analysis": f"Based on your income of ${income:,.0f}, {'you may be subject to AMT' if amt_liable else 'AMT is unlikely to apply'}.",
            "recommendation": "Consult a CPA for detailed AMT planning" if amt_liable else "No AMT action needed",
            "key_factors": ["income_level", "salt_deductions"],
            "action_items": ["Review SALT deduction impact on AMT"] if amt_liable else [],
            "confidence": 0.5,
            "ai_powered": False,
        }
    except Exception as e:
        logger.error(f"AMT analysis error: {e}")
        raise HTTPException(status_code=500, detail="Unable to perform AMT analysis.")
