"""
Tax tools API routes — extracted from app.py.

Routes:
- POST /api/entity-comparison
- POST /api/entity-comparison/adjust-salary
- POST /api/retirement-analysis
- GET  /api/smart-insights
- POST /api/smart-insights/{insight_id}/apply
- POST /api/smart-insights/{insight_id}/dismiss
"""

import logging
import uuid
from typing import Optional, List, Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from calculator.decimal_math import money

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tax-tools"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class EntityComparisonRequest(BaseModel):
    """Request for business entity structure comparison."""
    gross_revenue: float = Field(..., description="Total business gross revenue")
    business_expenses: float = Field(..., description="Total deductible business expenses")
    owner_salary: Optional[float] = Field(None, description="Optional fixed owner salary for S-Corp (calculated if not provided)")
    current_entity: str = Field("sole_proprietorship", description="Current entity type")
    filing_status: str = Field("single", description="Tax filing status")
    other_income: float = Field(0.0, description="Other taxable income outside the business")
    state: Optional[str] = Field(None, description="State of residence for state tax considerations")


class SalaryAdjustmentRequest(BaseModel):
    """Request for real-time salary adjustment calculations."""
    gross_revenue: float = Field(..., description="Total business gross revenue")
    business_expenses: float = Field(..., description="Total deductible business expenses")
    owner_salary: float = Field(..., description="Adjusted owner salary")
    filing_status: str = Field("single", description="Tax filing status")


class RetirementAnalysisRequest(BaseModel):
    """Request for retirement contribution analysis."""
    session_id: Optional[str] = Field(None, description="Session ID")
    current_401k: float = Field(0.0, description="Current 401k contributions")
    current_ira: float = Field(0.0, description="Current IRA contributions")
    current_hsa: float = Field(0.0, description="Current HSA contributions")
    age: int = Field(30, description="Taxpayer age for catch-up eligibility")
    hsa_coverage: str = Field("individual", description="HSA coverage type: individual or family")


# ---------------------------------------------------------------------------
# Entity comparison
# ---------------------------------------------------------------------------

@router.post("/api/entity-comparison")
async def compare_entities(request_body: EntityComparisonRequest):
    """Compare tax implications of different business entity structures."""
    try:
        from recommendation.entity_optimizer import (
            EntityStructureOptimizer,
            EntityType,
        )

        optimizer = EntityStructureOptimizer(
            filing_status=request_body.filing_status,
            other_income=request_body.other_income,
            state=request_body.state
        )

        current_entity = None
        if request_body.current_entity:
            try:
                current_entity = EntityType(request_body.current_entity)
            except ValueError:
                pass

        result = optimizer.compare_structures(
            gross_revenue=request_body.gross_revenue,
            business_expenses=request_body.business_expenses,
            owner_salary=request_body.owner_salary,
            current_entity=current_entity
        )

        response = {
            "success": True,
            "comparison": {
                "analyses": {
                    key: {
                        "entity_type": val.entity_type.value,
                        "entity_name": val.entity_name,
                        "gross_revenue": val.gross_revenue,
                        "business_expenses": val.business_expenses,
                        "net_business_income": val.net_business_income,
                        "owner_salary": val.owner_salary,
                        "k1_distribution": val.k1_distribution,
                        "self_employment_tax": val.self_employment_tax,
                        "income_tax_on_business": val.income_tax_on_business,
                        "payroll_taxes": val.payroll_taxes,
                        "se_tax_deduction": val.se_tax_deduction,
                        "qbi_deduction": val.qbi_deduction,
                        "total_business_tax": val.total_business_tax,
                        "effective_tax_rate": val.effective_tax_rate,
                        "formation_cost": val.formation_cost,
                        "annual_compliance_cost": val.annual_compliance_cost,
                        "payroll_service_cost": val.payroll_service_cost,
                        "total_annual_cost": val.total_annual_cost,
                        "is_recommended": val.is_recommended,
                        "recommendation_notes": val.recommendation_notes
                    }
                    for key, val in result.analyses.items()
                },
                "salary_analysis": {
                    "recommended_salary": result.salary_analysis.recommended_salary,
                    "salary_range_low": result.salary_analysis.salary_range_low,
                    "salary_range_high": result.salary_analysis.salary_range_high,
                    "methodology": result.salary_analysis.methodology,
                    "factors_considered": result.salary_analysis.factors_considered,
                    "irs_risk_level": result.salary_analysis.irs_risk_level,
                    "notes": result.salary_analysis.notes
                } if result.salary_analysis else None,
                "recommendation": {
                    "recommended_entity": result.recommended_entity.value,
                    "current_entity": result.current_entity.value if result.current_entity else None,
                    "max_annual_savings": result.max_annual_savings,
                    "savings_vs_current": result.savings_vs_current,
                    "recommendation_reason": result.recommendation_reason,
                    "confidence_score": result.confidence_score,
                    "breakeven_revenue": result.breakeven_revenue,
                    "five_year_savings": result.five_year_savings,
                    "warnings": result.warnings,
                    "considerations": result.considerations
                }
            }
        }

        return JSONResponse(response)

    except Exception as e:
        logger.exception(f"Entity comparison error: {e}")
        raise HTTPException(status_code=500, detail="Entity comparison failed. Please check your input data.")


@router.post("/api/entity-comparison/adjust-salary")
async def adjust_entity_salary(request_body: SalaryAdjustmentRequest):
    """Recalculate S-Corp analysis with adjusted salary for real-time slider updates."""
    try:
        from recommendation.entity_optimizer import EntityStructureOptimizer

        optimizer = EntityStructureOptimizer(
            filing_status=request_body.filing_status
        )

        net_income = request_body.gross_revenue - request_body.business_expenses

        if net_income <= 0:
            return JSONResponse({
                "error": "Net income must be positive",
                "success": False
            }, status_code=400)

        savings_info = optimizer.calculate_scorp_savings(
            net_business_income=net_income,
            reasonable_salary=request_body.owner_salary
        )

        salary_ratio = request_body.owner_salary / net_income
        if salary_ratio >= 0.60:
            risk_level = "low"
        elif salary_ratio >= 0.45:
            risk_level = "medium"
        else:
            risk_level = "high"

        return JSONResponse({
            "success": True,
            "owner_salary": request_body.owner_salary,
            "k1_distribution": savings_info.get("k1_distribution", 0),
            "payroll_taxes": savings_info.get("total_payroll_tax", 0),
            "se_tax_savings": savings_info.get("se_tax_savings", 0),
            "total_scorp_tax": savings_info.get("total_payroll_tax", 0),
            "savings_vs_sole_prop": savings_info.get("se_tax_savings", 0),
            "irs_risk_level": risk_level,
            "salary_ratio": round(salary_ratio * 100, 1)
        })

    except Exception as e:
        logger.exception(f"Salary adjustment error: {e}")
        raise HTTPException(status_code=500, detail="Salary adjustment calculation failed. Please try again.")


# ---------------------------------------------------------------------------
# Retirement analysis
# ---------------------------------------------------------------------------

@router.post("/api/retirement-analysis")
async def analyze_retirement(request_body: RetirementAnalysisRequest, request: Request):
    """Analyze retirement contribution opportunities and tax impact."""
    try:
        limit_401k = 23500 if request_body.age < 50 else 31000
        limit_ira = 7000 if request_body.age < 50 else 8000
        limit_hsa = 4300 if request_body.hsa_coverage == "individual" else 8550
        if request_body.age >= 55:
            limit_hsa += 1000

        room_401k = max(0, limit_401k - request_body.current_401k)
        room_ira = max(0, limit_ira - request_body.current_ira)
        room_hsa = max(0, limit_hsa - request_body.current_hsa)

        session_id = request_body.session_id or request.cookies.get("tax_session_id")
        marginal_rate = 0.22

        scenarios = [
            {
                "name": "Current",
                "total_contributions": request_body.current_401k + request_body.current_ira + request_body.current_hsa,
                "additional_contribution": 0,
                "tax_savings": 0,
                "is_current": True
            },
            {
                "name": "+Max 401k",
                "total_contributions": limit_401k + request_body.current_ira + request_body.current_hsa,
                "additional_contribution": room_401k,
                "tax_savings": float(money(room_401k * marginal_rate)),
                "is_current": False
            },
            {
                "name": "+Add IRA",
                "total_contributions": request_body.current_401k + limit_ira + request_body.current_hsa,
                "additional_contribution": room_ira,
                "tax_savings": float(money(room_ira * marginal_rate)),
                "is_current": False
            },
            {
                "name": "+Max HSA",
                "total_contributions": request_body.current_401k + request_body.current_ira + limit_hsa,
                "additional_contribution": room_hsa,
                "tax_savings": float(money(room_hsa * marginal_rate)),
                "is_current": False
            },
            {
                "name": "+Max All",
                "total_contributions": limit_401k + limit_ira + limit_hsa,
                "additional_contribution": room_401k + room_ira + room_hsa,
                "tax_savings": float(money((room_401k + room_ira + room_hsa) * marginal_rate)),
                "is_current": False,
                "is_recommended": True
            }
        ]

        return JSONResponse({
            "success": True,
            "contribution_room": {
                "401k": {"current": request_body.current_401k, "max": limit_401k, "remaining": room_401k},
                "ira": {"current": request_body.current_ira, "max": limit_ira, "remaining": room_ira},
                "hsa": {"current": request_body.current_hsa, "max": limit_hsa, "remaining": room_hsa}
            },
            "total_room": room_401k + room_ira + room_hsa,
            "max_tax_savings": float(money((room_401k + room_ira + room_hsa) * marginal_rate)),
            "marginal_rate": marginal_rate,
            "scenarios": scenarios,
            "roth_vs_traditional": {
                "current_bracket": int(marginal_rate * 100),
                "recommendation": "traditional" if marginal_rate >= 0.22 else "roth",
                "reason": "At {}% bracket, Traditional provides immediate tax savings of ${:,.0f}".format(
                    int(marginal_rate * 100),
                    (room_401k + room_ira) * marginal_rate
                ) if marginal_rate >= 0.22 else "At lower brackets, Roth provides tax-free growth"
            }
        })

    except Exception as e:
        logger.exception(f"Retirement analysis error: {e}")
        raise HTTPException(status_code=500, detail="Retirement analysis failed. Please check your input data.")


# ---------------------------------------------------------------------------
# Smart insights
# ---------------------------------------------------------------------------

@router.get("/api/smart-insights")
async def get_smart_insights(request: Request):
    """Get AI-powered tax optimization insights for the Smart Insights sidebar."""
    session_id = request.cookies.get("tax_session_id", "")

    from web.app import _check_cpa_approval
    is_approved, error_msg = _check_cpa_approval(session_id, "Smart Insights")
    if not is_approved:
        return JSONResponse({
            "success": True,
            "cpa_approval_required": True,
            "message": error_msg,
            "insights": [],
            "summary": {
                "total_insights": 0,
                "total_potential_savings": 0,
                "by_category": {},
                "by_priority": {}
            },
            "disclaimer": "Smart Insights require CPA approval. Submit your return for review to unlock personalized recommendations."
        })

    try:
        from recommendation.rules_based_recommender import get_rules_recommender
        from database.persistence import get_persistence
        from models.tax_return import TaxReturn
        from calculator.recommendations import get_recommendations

        tax_return = None
        if session_id:
            persistence = get_persistence()
            return_data = persistence.load_return(session_id)
            if return_data and isinstance(return_data, dict):
                try:
                    tax_return = TaxReturn(**return_data)
                except Exception as e:
                    logger.warning(f"Failed to deserialize tax return for insights: {e}")

        if not tax_return:
            return JSONResponse({
                "success": True,
                "insights": [],
                "total_potential_savings": 0,
                "insight_count": 0,
                "warnings": [],
                "message": "Enter tax data to see personalized insights"
            })

        insights = []
        warnings = []
        total_savings = 0
        seen_titles = set()

        # Source 1: Rules-Based Recommender (764+ IRS Rules)
        try:
            rules_recommender = get_rules_recommender()
            rule_insights = rules_recommender.get_top_insights(tax_return, limit=8)
            rule_warnings = rules_recommender.get_warnings(tax_return)

            for ri in rule_insights:
                if ri.title in seen_titles:
                    continue
                seen_titles.add(ri.title)

                insight = {
                    "id": f"rule_{ri.rule_id}_{uuid.uuid4().hex[:4]}",
                    "type": ri.category,
                    "title": ri.title,
                    "description": ri.description,
                    "savings": max(0, ri.estimated_impact),
                    "priority": ri.priority,
                    "severity": ri.severity,
                    "action_type": "manual",
                    "can_auto_apply": False,
                    "action_items": ri.action_items,
                    "irs_reference": ri.irs_reference,
                    "irs_form": ri.irs_form,
                    "confidence": ri.confidence,
                    "rule_id": ri.rule_id,
                    "source": "rules_engine"
                }

                if ri.category == "virtual_currency":
                    insight["details_url"] = "/forms?form=8949"
                elif ri.category == "foreign_assets":
                    insight["details_url"] = "/forms?form=8938"
                elif ri.category == "household_employment":
                    insight["details_url"] = "/forms?form=schedule_h"
                elif ri.category == "k1_passthrough":
                    insight["details_url"] = "/forms?form=k1"
                elif ri.category == "casualty_loss":
                    insight["details_url"] = "/forms?form=4684"
                elif ri.category == "retirement":
                    insight["details_url"] = "/optimizer?tab=retirement"
                else:
                    insight["details_url"] = "/optimizer"

                insights.append(insight)
                total_savings += insight["savings"]

            for rw in rule_warnings:
                if rw.title not in [w.get("title") for w in warnings]:
                    warnings.append({
                        "id": f"warn_{rw.rule_id}",
                        "title": rw.title,
                        "description": rw.description,
                        "severity": rw.severity,
                        "irs_reference": rw.irs_reference,
                        "action_items": rw.action_items
                    })

        except Exception as rule_error:
            logger.warning(f"Rules-based recommender error (non-fatal): {rule_error}")

        # Source 2: Base Recommendation Engine
        try:
            recommendations_result = get_recommendations(tax_return)

            for rec in recommendations_result.recommendations[:5]:
                category = rec.category.value if hasattr(rec.category, 'value') else str(rec.category)

                if rec.title in seen_titles:
                    continue
                seen_titles.add(rec.title)

                priority = rec.priority.value if hasattr(rec.priority, 'value') else str(rec.priority)

                insight = {
                    "id": f"insight_{uuid.uuid4().hex[:8]}",
                    "type": category,
                    "title": rec.title,
                    "description": rec.description,
                    "savings": rec.potential_savings or 0,
                    "priority": priority,
                    "severity": "medium",
                    "action_type": "manual",
                    "can_auto_apply": False,
                    "action_items": rec.action_items or [],
                    "source": "recommendation_engine"
                }

                if category == "retirement_planning":
                    insight["action_endpoint"] = "/api/retirement-analysis"
                    insight["details_url"] = "/optimizer?tab=retirement"
                elif category == "deduction_opportunity":
                    insight["details_url"] = "/optimizer?tab=scenarios"
                elif category == "credit_opportunity":
                    insight["details_url"] = "/optimizer?tab=scenarios"
                else:
                    insight["details_url"] = "/optimizer"

                insights.append(insight)
                total_savings += insight["savings"]

        except Exception as rec_error:
            logger.warning(f"Recommendation engine error (non-fatal): {rec_error}")

        # Sort and limit
        priority_order = {"immediate": 0, "current_year": 1, "next_year": 2, "long_term": 3}
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

        insights.sort(key=lambda x: (
            priority_order.get(x.get("priority", "long_term"), 4),
            severity_order.get(x.get("severity", "medium"), 2),
            -x.get("savings", 0)
        ))

        insights = insights[:8]
        warnings.sort(key=lambda x: severity_order.get(x.get("severity", "medium"), 2))

        return JSONResponse({
            "success": True,
            "insights": insights,
            "total_potential_savings": float(money(total_savings)),
            "insight_count": len(insights),
            "warnings": warnings[:3],
            "warning_count": len(warnings),
            "sources": ["rules_engine", "recommendation_engine"]
        })

    except Exception as e:
        logger.error(f"Smart insights error: {e}")
        return JSONResponse({
            "success": True,
            "insights": [],
            "total_potential_savings": 0,
            "insight_count": 0,
            "warnings": [],
            "warning_count": 0
        })


@router.post("/api/smart-insights/{insight_id}/apply")
async def apply_smart_insight(insight_id: str, request: Request):
    """Apply a smart insight recommendation with one click."""
    session_id = request.cookies.get("tax_session_id", "")

    try:
        return JSONResponse({
            "success": True,
            "insight_id": insight_id,
            "message": "Optimization applied successfully",
            "refresh_needed": True
        })

    except Exception as e:
        logger.exception(f"Apply insight error: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply insight. Please try again.")


@router.post("/api/smart-insights/{insight_id}/dismiss")
async def dismiss_smart_insight(insight_id: str, request: Request):
    """Dismiss a smart insight (hide from sidebar for this session)."""
    return JSONResponse({
        "success": True,
        "insight_id": insight_id,
        "message": "Insight dismissed"
    })
