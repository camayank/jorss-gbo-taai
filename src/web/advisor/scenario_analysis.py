"""
Scenario analysis endpoints extracted from intelligent_advisor_api.py.

Contains:
- POST /roth-analysis
- POST /entity-analysis
- POST /deduction-analysis
- POST /amt-analysis
- GET  /audit-risk/{session_id}
- POST /multi-year-planning
- POST /estate-planning
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
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "scenario_roth_analysis",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives basic bracket comparison instead of AI Roth analysis",
                    },
                )

        # Deterministic fallback with real calculations
        from services.ai.tax_reasoning_service import get_tax_reasoning_service
        reasoning = get_tax_reasoning_service()
        result = reasoning._deterministic_roth_analysis(
            traditional_balance=profile.get("traditional_ira_balance", 0) or 50000,
            current_bracket=calculation.marginal_rate / 100,
            projected_bracket=max(calculation.marginal_rate - 5, 10) / 100,
            years_to_retirement=max(65 - (profile.get("age", 40) or 40), 5),
            filing_status=profile.get("filing_status", "single"),
        )
        return {
            "session_id": request.session_id,
            "analysis": result.analysis[:1500],
            "recommendation": result.recommendation,
            "key_factors": result.key_factors,
            "action_items": result.action_items[:5],
            "risks": result.risks,
            "confidence": result.confidence,
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
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "scenario_entity_analysis",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives basic Sole Prop vs S-Corp comparison instead of AI analysis",
                    },
                )

        # Deterministic fallback with real calculations
        from services.ai.tax_reasoning_service import get_tax_reasoning_service
        reasoning = get_tax_reasoning_service()
        result = reasoning._deterministic_entity_analysis(
            gross_revenue=business_income,
            business_expenses=profile.get("business_expenses", 0) or business_income * 0.3,
            owner_salary=business_income * 0.6,
            filing_status=profile.get("filing_status", "single"),
        )
        return {
            "session_id": request.session_id,
            "analysis": result.analysis[:1500],
            "recommendation": result.recommendation,
            "key_factors": result.key_factors,
            "action_items": result.action_items[:5],
            "risks": result.risks,
            "confidence": result.confidence,
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
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "scenario_deduction_analysis",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives standard vs itemized comparison instead of AI deduction strategy",
                    },
                )

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
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "scenario_audit_risk",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives rule-based risk score instead of AI audit assessment",
                    },
                )

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
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "scenario_amt_analysis",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives basic AMT estimate instead of AI AMT analysis",
                    },
                )

        # Deterministic fallback with real AMT calculation
        from services.ai.tax_reasoning_service import get_tax_reasoning_service
        reasoning = get_tax_reasoning_service()
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        salt = min(
            (profile.get("state_income_tax", 0) or 0) + (profile.get("property_taxes", 0) or 0),
            10000,
        )
        result = reasoning._deterministic_amt_analysis(
            regular_income=income,
            salt_deduction=salt,
            misc_deductions=profile.get("medical_expenses", 0) or 0,
            iso_spread=0,
            filing_status=filing_status,
        )
        return {
            "session_id": request.session_id,
            "analysis": result.analysis[:1500],
            "recommendation": result.recommendation,
            "key_factors": result.key_factors,
            "action_items": result.action_items[:5],
            "confidence": result.confidence,
            "ai_powered": False,
        }
    except Exception as e:
        logger.error(f"AMT analysis error: {e}")
        raise HTTPException(status_code=500, detail="Unable to perform AMT analysis.")


@router.post("/multi-year-planning")
async def analyze_multi_year(request=None, _session: str = Depends(verify_session_token)):
    """AI-powered multi-year tax strategy planning."""
    from web.intelligent_advisor_api import (
        chat_engine, AI_CHAT_ENABLED, STANDARD_DISCLAIMER,
    )

    try:
        profile = request.profile.dict(exclude_none=True)
        calculation = await chat_engine.get_tax_calculation(profile)
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        age = profile.get("age", 40) or 40
        years_to_retirement = max(65 - age, 5)

        if AI_CHAT_ENABLED:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()

                current_situation = (
                    f"Filing status: {filing_status}, AGI: ${income:,.0f}, "
                    f"Age: {age}, Marginal rate: {calculation.marginal_rate}%"
                )
                life_events = profile.get("life_events", "None specified")
                goals = profile.get("financial_goals", "Minimize taxes and build wealth")

                result = await reasoning.analyze_multi_year_strategy(
                    current_situation=current_situation,
                    life_events=str(life_events),
                    goals=str(goals),
                    years=min(years_to_retirement, 10),
                )
                return {
                    "session_id": request.session_id,
                    "analysis": result.analysis[:2000],
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
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "scenario_multi_year",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives rule-based multi-year projection instead of AI strategy",
                    },
                )

        # Deterministic fallback: 5-year projection with bracket creep
        growth_rate = 0.03  # 3% annual income growth
        projections = []
        projected_income = income
        for year in range(1, 6):
            projected_income *= (1 + growth_rate)
            projections.append({
                "year": year,
                "projected_income": round(projected_income),
                "bracket_note": f"{'Watch for bracket creep' if projected_income > income * 1.1 else 'Stable bracket'}",
            })

        # Retirement contribution room
        max_401k = 23500
        current_401k = profile.get("retirement_401k", 0) or 0
        catch_up = 7500 if age >= 50 else 0
        available_401k = max_401k + catch_up - current_401k

        analysis = f"""## Multi-Year Tax Strategy ({min(years_to_retirement, 5)}-Year Outlook)

**Current Position:** ${income:,.0f} income, {calculation.marginal_rate}% marginal rate

### Year-by-Year Income Projections (3% growth)
"""
        for p in projections:
            analysis += f"- Year {p['year']}: ${p['projected_income']:,.0f} — {p['bracket_note']}\n"

        analysis += f"""
### Key Strategies
1. **Maximize retirement contributions:** ${available_401k:,.0f} available in 401(k){' (including $7,500 catch-up)' if catch_up else ''}
2. **Bracket management:** Current rate {calculation.marginal_rate}%. Consider timing income/deductions to stay in lower brackets.
3. **Roth conversion ladder:** {'Consider partial conversions before retirement' if years_to_retirement > 10 else 'Limited time — evaluate full conversion'}
4. **Charitable bunching:** If itemizing is close to standard deduction, bundle 2 years of giving into 1 year
5. **HSA strategy:** Triple tax advantage — contribute max, invest, use in retirement"""

        return {
            "session_id": request.session_id,
            "analysis": analysis,
            "recommendation": f"Focus on maximizing tax-advantaged accounts (${available_401k:,.0f} 401k room available)",
            "key_factors": [
                f"Current income: ${income:,.0f}",
                f"Marginal rate: {calculation.marginal_rate}%",
                f"Years to retirement: {years_to_retirement}",
                f"401(k) room: ${available_401k:,.0f}",
            ],
            "action_items": [
                f"Increase 401(k) contributions — ${available_401k:,.0f} room available",
                "Review Roth conversion opportunity this year",
                "Evaluate charitable bunching strategy",
                "Consider HSA contributions if eligible",
            ],
            "confidence": 0.6,
            "disclaimer": STANDARD_DISCLAIMER,
        }
    except Exception as e:
        logger.error(f"Multi-year planning error: {e}")
        raise HTTPException(status_code=500, detail="Unable to complete multi-year analysis.")


@router.post("/estate-planning")
async def analyze_estate_plan(request=None, _session: str = Depends(verify_session_token)):
    """AI-powered estate tax and planning analysis."""
    from web.intelligent_advisor_api import (
        chat_engine, AI_CHAT_ENABLED, STANDARD_DISCLAIMER,
    )

    try:
        profile = request.profile.dict(exclude_none=True)
        income = profile.get("total_income", 0) or 0
        filing_status = profile.get("filing_status", "single")
        age = profile.get("age", 40) or 40

        # Estimate estate value from available data
        estate_value = profile.get("estate_value", 0) or 0
        if estate_value == 0:
            # Rough estimate from income and age
            estate_value = income * max(age - 25, 5) * 0.3

        if AI_CHAT_ENABLED:
            try:
                from services.ai.tax_reasoning_service import get_tax_reasoning_service
                reasoning = get_tax_reasoning_service()
                result = await reasoning.analyze_estate_plan(
                    estate_value=estate_value,
                    annual_gifting=profile.get("annual_gifting", 0) or 0,
                    trusts=profile.get("trusts", "None"),
                    beneficiaries=profile.get("beneficiaries", "Not specified"),
                    state=profile.get("state", "CA"),
                    goals=profile.get("estate_goals", "Minimize estate taxes and transfer wealth efficiently"),
                )
                return {
                    "session_id": request.session_id,
                    "analysis": result.analysis[:2000],
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
                logger.warning(
                    "AI fallback activated",
                    extra={
                        "service": "scenario_estate_planning",
                        "source": "fallback",
                        "reason": str(e),
                        "impact": "user receives rule-based estate analysis instead of AI estate planning",
                    },
                )

        # Deterministic fallback: basic estate tax calculations
        # 2024 federal estate tax exemption
        is_married = filing_status in ("married_filing_jointly", "married_filing_separately")
        federal_exemption = 13610000  # 2024 individual exemption
        combined_exemption = federal_exemption * 2 if is_married else federal_exemption
        annual_gift_exclusion = 18000  # 2024 per-recipient annual exclusion
        gift_split = annual_gift_exclusion * 2 if is_married else annual_gift_exclusion

        taxable_estate = max(0, estate_value - combined_exemption)
        estate_tax = taxable_estate * 0.40  # 40% top estate tax rate

        # Generation-skipping transfer tax exemption matches estate exemption
        gst_exemption = combined_exemption

        analysis = f"""## Estate Planning Analysis

**Estimated Estate Value:** ${estate_value:,.0f}

### Federal Estate Tax
- Exemption ({'' if not is_married else 'combined '}2024): ${combined_exemption:,.0f}
- Taxable estate: ${taxable_estate:,.0f}
- Estimated estate tax (40%): ${estate_tax:,.0f}
- **Status:** {'Estate likely subject to federal estate tax' if taxable_estate > 0 else 'Below federal exemption — no federal estate tax expected'}

### Annual Gifting Strategy
- Annual gift exclusion: ${annual_gift_exclusion:,.0f} per recipient{' ($' + f'{gift_split:,.0f} with gift splitting)' if is_married else ''}
- Gifts within exclusion don't reduce lifetime exemption
- Consider systematic gifting program to reduce estate

### Key Planning Opportunities
1. **Annual gifts:** Gift ${annual_gift_exclusion:,.0f}/recipient/year to reduce estate tax-free
2. **529 plans:** Front-load 5 years of gifts (${annual_gift_exclusion * 5:,.0f}) per beneficiary
3. **Charitable remainder trust:** Income stream + estate reduction + charitable deduction
4. **Irrevocable life insurance trust (ILIT):** Remove insurance proceeds from estate
5. **Step-up in basis:** Appreciated assets receive stepped-up basis at death — plan accordingly

### State Considerations
- Some states have lower estate tax exemptions (e.g., OR: $1M, MA: $2M, NY: $6.94M)
- Check your state's estate/inheritance tax rules"""

        return {
            "session_id": request.session_id,
            "analysis": analysis,
            "recommendation": (
                f"Estate of ${estate_value:,.0f} is {'above' if taxable_estate > 0 else 'below'} "
                f"the federal exemption. {'Active estate planning recommended.' if taxable_estate > 0 else 'Focus on annual gifting and basis planning.'}"
            ),
            "key_factors": [
                f"Estimated estate: ${estate_value:,.0f}",
                f"Federal exemption: ${combined_exemption:,.0f}",
                f"Taxable estate: ${taxable_estate:,.0f}",
                f"Annual gift exclusion: ${annual_gift_exclusion:,.0f}/recipient",
            ],
            "action_items": [
                f"Utilize ${annual_gift_exclusion:,.0f}/recipient annual gift exclusion",
                "Review beneficiary designations on retirement accounts and insurance",
                "Consider trust structures for estate tax reduction",
                "Evaluate state-specific estate tax implications",
                "Consult estate planning attorney for comprehensive plan",
            ],
            "confidence": 0.55,
            "requires_professional_review": True,
            "disclaimer": STANDARD_DISCLAIMER,
        }
    except Exception as e:
        logger.error(f"Estate planning error: {e}")
        raise HTTPException(status_code=500, detail="Unable to complete estate planning analysis.")
