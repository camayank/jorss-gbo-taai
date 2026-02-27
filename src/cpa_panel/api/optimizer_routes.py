"""
CPA Panel Optimizer Routes

API endpoints for tax optimization analysis including credit analysis,
deduction optimization, filing status comparison, entity structure
analysis, and comprehensive tax strategy.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from dataclasses import asdict

logger = logging.getLogger(__name__)

optimizer_router = APIRouter(tags=["Tax Optimization"])


def get_optimizer_adapter():
    """Get the optimizer adapter singleton."""
    from cpa_panel.adapters.optimizer_adapter import get_optimizer_adapter
    return get_optimizer_adapter()


# =============================================================================
# CREDIT ANALYSIS
# =============================================================================

@optimizer_router.post("/session/{session_id}/credits/analyze")
async def analyze_credits(session_id: str, request: Request):
    """
    Analyze all potential tax credits for a client.

    Returns comprehensive credit eligibility analysis including:
    - Eligible credits with amounts
    - Ineligible credits with reasons
    - Near-miss credits (close to qualifying)
    - Action items to maximize credits
    """
    try:
        adapter = get_optimizer_adapter()
        result = adapter.get_credit_analysis(session_id)

        return JSONResponse({
            "success": result.success,
            "session_id": result.session_id,
            "analysis_type": result.analysis_type,
            "timestamp": result.timestamp,
            "summary": result.summary,
            "total_potential_savings": result.total_potential_savings,
            "confidence": result.confidence,
            "data": result.data,
            "warnings": result.warnings,
            "recommendations": result.recommendations,
        })

    except Exception as e:
        logger.error(f"Credit analysis error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# =============================================================================
# DEDUCTION ANALYSIS
# =============================================================================

@optimizer_router.post("/session/{session_id}/deductions/analyze")
async def analyze_deductions(session_id: str, request: Request):
    """
    Analyze standard vs itemized deduction strategy.

    Returns comprehensive deduction analysis including:
    - Standard deduction amount
    - Itemized deduction breakdown
    - Recommended strategy
    - Bunching strategy viability
    - Tax savings estimate
    """
    try:
        adapter = get_optimizer_adapter()
        result = adapter.get_deduction_analysis(session_id)

        return JSONResponse({
            "success": result.success,
            "session_id": result.session_id,
            "analysis_type": result.analysis_type,
            "timestamp": result.timestamp,
            "summary": result.summary,
            "total_potential_savings": result.total_potential_savings,
            "confidence": result.confidence,
            "data": result.data,
            "warnings": result.warnings,
            "recommendations": result.recommendations,
        })

    except Exception as e:
        logger.error(f"Deduction analysis error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# =============================================================================
# FILING STATUS COMPARISON
# =============================================================================

@optimizer_router.post("/session/{session_id}/filing-status/compare")
async def compare_filing_status(session_id: str, request: Request):
    """
    Compare tax implications of all eligible filing statuses.

    Returns filing status analysis including:
    - Tax liability for each eligible status
    - Recommended status with reason
    - Potential savings from optimal choice
    - Benefits and drawbacks of each option
    """
    try:
        adapter = get_optimizer_adapter()
        result = adapter.get_filing_status_comparison(session_id)

        return JSONResponse({
            "success": result.success,
            "session_id": result.session_id,
            "analysis_type": result.analysis_type,
            "timestamp": result.timestamp,
            "summary": result.summary,
            "total_potential_savings": result.total_potential_savings,
            "confidence": result.confidence,
            "data": result.data,
            "warnings": result.warnings,
            "recommendations": result.recommendations,
        })

    except Exception as e:
        logger.error(f"Filing status comparison error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# =============================================================================
# ENTITY STRUCTURE COMPARISON
# =============================================================================

@optimizer_router.post("/session/{session_id}/entity/compare")
async def compare_entity_structures(session_id: str, request: Request):
    """
    Compare business entity structures (Sole Prop vs LLC vs S-Corp).

    Request body (optional):
        - gross_revenue: Override gross revenue
        - business_expenses: Override business expenses
        - owner_salary: Specify owner salary for S-Corp analysis

    Returns entity analysis including:
    - Tax liability for each structure
    - Recommended entity type
    - S-Corp reasonable salary analysis
    - 5-year savings projection
    - Formation and compliance costs
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    gross_revenue = body.get("gross_revenue")
    business_expenses = body.get("business_expenses")
    owner_salary = body.get("owner_salary")

    try:
        adapter = get_optimizer_adapter()
        result = adapter.get_entity_comparison(
            session_id,
            gross_revenue=gross_revenue,
            business_expenses=business_expenses,
            owner_salary=owner_salary,
        )

        return JSONResponse({
            "success": result.success,
            "session_id": result.session_id,
            "analysis_type": result.analysis_type,
            "timestamp": result.timestamp,
            "summary": result.summary,
            "total_potential_savings": result.total_potential_savings,
            "confidence": result.confidence,
            "data": result.data,
            "warnings": result.warnings,
            "recommendations": result.recommendations,
        })

    except Exception as e:
        logger.error(f"Entity comparison error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# =============================================================================
# COMPREHENSIVE STRATEGY ANALYSIS
# =============================================================================

@optimizer_router.post("/session/{session_id}/strategy/analyze")
async def analyze_full_strategy(session_id: str, request: Request):
    """
    Generate comprehensive tax strategy analysis.

    Returns complete strategy report including:
    - Retirement contribution analysis
    - Investment tax strategies
    - Strategies by priority (immediate, current year, next year, long-term)
    - Total potential savings
    - Top three recommendations
    """
    try:
        adapter = get_optimizer_adapter()
        result = adapter.get_full_strategy(session_id)

        return JSONResponse({
            "success": result.success,
            "session_id": result.session_id,
            "analysis_type": result.analysis_type,
            "timestamp": result.timestamp,
            "summary": result.summary,
            "total_potential_savings": result.total_potential_savings,
            "confidence": result.confidence,
            "data": result.data,
            "warnings": result.warnings,
            "recommendations": result.recommendations,
        })

    except Exception as e:
        logger.error(f"Strategy analysis error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


# =============================================================================
# COMBINED ANALYSIS (ALL OPTIMIZERS)
# =============================================================================

@optimizer_router.get("/session/{session_id}/optimization/summary")
async def get_optimization_summary(session_id: str, request: Request):
    """
    Get a summary of all available optimizations for a client.

    Provides a quick overview without running full analysis:
    - Available optimizer types
    - Basic client info
    - Quick savings indicators
    """
    try:
        adapter = get_optimizer_adapter()
        tax_return = adapter.get_tax_return(session_id)

        if not tax_return:
            raise HTTPException(status_code=404, detail=f"Tax return not found: {session_id}")

        # Quick summary without full analysis
        agi = tax_return.adjusted_gross_income or 0
        filing_status = tax_return.taxpayer.filing_status.value if tax_return.taxpayer.filing_status else "unknown"

        # Check what optimizations might be relevant
        income = tax_return.income
        has_self_employment = getattr(income, 'self_employment_income', 0) > 0
        has_investments = (
            getattr(income, 'interest_income', 0) > 0 or
            getattr(income, 'ordinary_dividends', 0) > 0 or
            getattr(income, 'long_term_capital_gains', 0) > 0
        )
        has_dependents = bool(tax_return.dependents)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            "client_summary": {
                "adjusted_gross_income": agi,
                "filing_status": filing_status,
                "has_self_employment": has_self_employment,
                "has_investments": has_investments,
                "has_dependents": has_dependents,
            },
            "available_analyses": {
                "credits": {
                    "available": True,
                    "relevance": "high" if has_dependents or agi < 200000 else "medium",
                    "description": "Analyze all eligible tax credits",
                },
                "deductions": {
                    "available": True,
                    "relevance": "high",
                    "description": "Standard vs itemized deduction analysis",
                },
                "filing_status": {
                    "available": True,
                    "relevance": "medium",
                    "description": "Compare eligible filing status options",
                },
                "entity": {
                    "available": has_self_employment,
                    "relevance": "high" if has_self_employment else "none",
                    "description": "Business structure optimization (S-Corp vs Sole Prop)",
                },
                "strategy": {
                    "available": True,
                    "relevance": "high",
                    "description": "Comprehensive tax planning strategies",
                },
            },
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Optimization summary error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")
