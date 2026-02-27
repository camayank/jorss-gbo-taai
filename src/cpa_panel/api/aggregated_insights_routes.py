"""
Aggregated Insights API Routes for CPA Dashboard

Provides aggregated insights across ALL clients for the CPA dashboard.
This connects the real recommendation engine to the dashboard UI.

Key difference from /api/smart-insights:
- /api/smart-insights: Single client (session-based)
- /api/cpa/insights/aggregate: All clients for a preparer/tenant
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .auth_dependencies import require_internal_cpa_auth
from .common import format_success_response, format_error_response, get_tenant_id
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["aggregated-insights"])


@router.get("/aggregate", dependencies=[Depends(require_internal_cpa_auth)])
async def get_aggregated_insights(
    request: Request,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Get aggregated insights across all clients for CPA dashboard.

    This endpoint connects the REAL recommendation engine to generate
    insights across all clients, aggregated for the CPA dashboard view.

    Returns:
    - Total savings potential across all clients
    - Top insights by savings amount
    - Insights by category breakdown
    - Per-client savings summary
    """
    tenant_id = get_tenant_id(request)
    preparer_id = request.headers.get("X-Preparer-ID", "default")

    try:
        # Get all sessions/returns for this tenant
        from src.database.session_persistence import get_session_persistence
        from cpa_panel.adapters import TaxReturnAdapter

        persistence = get_session_persistence()
        sessions = persistence.list_sessions(tenant_id)

        # Also get sessions from return_status table (CPA workflow)
        returns_in_review = persistence.list_returns_by_status("IN_REVIEW", tenant_id)
        returns_approved = persistence.list_returns_by_status("CPA_APPROVED", tenant_id)
        returns_draft = persistence.list_returns_by_status("DRAFT", tenant_id)

        # Combine all session IDs
        all_session_ids = set()
        for session in sessions:
            if hasattr(session, 'session_id'):
                all_session_ids.add(session.session_id)
            elif isinstance(session, dict):
                all_session_ids.add(session.get('session_id'))

        for ret in returns_in_review + returns_approved + returns_draft:
            all_session_ids.add(ret.get('session_id'))

        # Get recommendations for each return
        adapter = TaxReturnAdapter()
        all_insights = []
        client_summaries = []
        total_savings = 0

        # Import recommendation engines
        from calculator.recommendations import get_recommendations, RecommendationCategory

        # Try to use rules-based recommender too
        try:
            from recommendation.rules_based_recommender import RulesBasedRecommender
            rules_recommender = RulesBasedRecommender()
            has_rules_recommender = True
        except ImportError:
            rules_recommender = None
            has_rules_recommender = False

        for session_id in all_session_ids:
            tax_return = adapter.get_tax_return(session_id)
            if not tax_return:
                continue

            # Get client name for attribution
            client_name = _extract_client_name(tax_return)
            client_savings = 0

            # Get base recommendations
            try:
                result = get_recommendations(tax_return)
                for rec in result.recommendations:
                    savings = rec.potential_savings or 0
                    client_savings += savings
                    total_savings += savings

                    all_insights.append({
                        "id": f"{session_id}_{rec.title[:20]}",
                        "session_id": session_id,
                        "client_name": client_name,
                        "title": rec.title,
                        "description": rec.description,
                        "category": rec.category.value if hasattr(rec.category, 'value') else rec.category,
                        "priority": rec.priority.value if hasattr(rec.priority, 'value') else rec.priority,
                        "estimated_savings": savings,
                        "action_items": rec.action_items,
                        "irs_reference": "",  # Base recommender doesn't have IRS refs
                        "source": "recommendation_engine",
                    })
            except Exception as e:
                logger.warning(f"Error getting base recommendations for {session_id}: {e}")

            # Get rules-based insights (has IRS references)
            if has_rules_recommender and rules_recommender:
                try:
                    rule_insights = rules_recommender.get_top_insights(tax_return, limit=10)
                    for insight in rule_insights:
                        savings = insight.estimated_impact or 0
                        if savings > 0:
                            client_savings += savings
                            total_savings += savings

                        all_insights.append({
                            "id": f"{session_id}_{insight.rule_id}",
                            "session_id": session_id,
                            "client_name": client_name,
                            "title": insight.title,
                            "description": insight.description,
                            "category": insight.category,
                            "priority": insight.priority,
                            "estimated_savings": savings,
                            "action_items": insight.action_items,
                            "irs_reference": insight.irs_reference,
                            "irs_form": insight.irs_form,
                            "rule_id": insight.rule_id,
                            "confidence": insight.confidence,
                            "source": "rules_engine",
                        })
                except Exception as e:
                    logger.warning(f"Error getting rules insights for {session_id}: {e}")

            # Add client summary
            if client_savings > 0:
                client_summaries.append({
                    "session_id": session_id,
                    "client_name": client_name,
                    "total_savings": float(money(client_savings)),
                })

        # Sort insights by savings (descending)
        all_insights.sort(key=lambda x: x.get("estimated_savings", 0), reverse=True)

        # Limit results
        top_insights = all_insights[:limit]

        # Calculate category breakdown
        category_breakdown = _calculate_category_breakdown(all_insights)

        # Sort clients by savings
        client_summaries.sort(key=lambda x: x["total_savings"], reverse=True)

        return format_success_response({
            "total_savings_potential": float(money(total_savings)),
            "total_clients_analyzed": len(all_session_ids),
            "total_insights": len(all_insights),
            "insights": top_insights,
            "category_breakdown": category_breakdown,
            "clients_by_savings": client_summaries[:20],  # Top 20 clients
            "generated_at": datetime.utcnow().isoformat(),
            "has_rules_engine": has_rules_recommender,
        })

    except Exception as e:
        logger.error(f"Error getting aggregated insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", dependencies=[Depends(require_internal_cpa_auth)])
async def get_insights_by_category(
    request: Request,
) -> Dict[str, Any]:
    """
    Get insights grouped by optimization category.

    Categories:
    - retirement_planning: IRA, 401(k), HSA opportunities
    - deduction_opportunity: Itemized vs standard, bunching
    - credit_opportunity: Child tax credit, education credits
    - investment_strategy: Capital gains, dividends
    - timing_optimization: Bracket management, income timing
    - warnings: Underpayment, compliance issues
    """
    tenant_id = get_tenant_id(request)

    try:
        # Get all aggregated insights first
        from src.database.session_persistence import get_session_persistence
        from cpa_panel.adapters import TaxReturnAdapter
        from calculator.recommendations import get_recommendations

        persistence = get_session_persistence()
        sessions = persistence.list_sessions(tenant_id)

        adapter = TaxReturnAdapter()
        categories = {
            "retirement_planning": {"insights": [], "total_savings": 0, "client_count": 0},
            "deduction_opportunity": {"insights": [], "total_savings": 0, "client_count": 0},
            "credit_opportunity": {"insights": [], "total_savings": 0, "client_count": 0},
            "investment_strategy": {"insights": [], "total_savings": 0, "client_count": 0},
            "timing_optimization": {"insights": [], "total_savings": 0, "client_count": 0},
            "warning": {"insights": [], "total_savings": 0, "client_count": 0},
            "informational": {"insights": [], "total_savings": 0, "client_count": 0},
        }

        clients_by_category = {cat: set() for cat in categories}

        for session in sessions:
            session_id = session.session_id if hasattr(session, 'session_id') else session.get('session_id')
            if not session_id:
                continue

            tax_return = adapter.get_tax_return(session_id)
            if not tax_return:
                continue

            client_name = _extract_client_name(tax_return)

            try:
                result = get_recommendations(tax_return)
                for rec in result.recommendations:
                    cat_key = rec.category.value if hasattr(rec.category, 'value') else rec.category
                    if cat_key not in categories:
                        cat_key = "informational"

                    savings = rec.potential_savings or 0
                    categories[cat_key]["total_savings"] += savings
                    clients_by_category[cat_key].add(session_id)

                    categories[cat_key]["insights"].append({
                        "session_id": session_id,
                        "client_name": client_name,
                        "title": rec.title,
                        "savings": savings,
                        "priority": rec.priority.value if hasattr(rec.priority, 'value') else rec.priority,
                    })
            except Exception as e:
                logger.warning(f"Error processing {session_id}: {e}")

        # Update client counts
        for cat_key in categories:
            categories[cat_key]["client_count"] = len(clients_by_category[cat_key])
            categories[cat_key]["total_savings"] = float(money(categories[cat_key]["total_savings"]))
            # Sort insights by savings
            categories[cat_key]["insights"].sort(key=lambda x: x.get("savings", 0), reverse=True)
            # Limit to top 10 per category
            categories[cat_key]["insights"] = categories[cat_key]["insights"][:10]

        return format_success_response({
            "categories": categories,
        })

    except Exception as e:
        logger.error(f"Error getting insights by category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client/{session_id}", dependencies=[Depends(require_internal_cpa_auth)])
async def get_client_insights(
    request: Request,
    session_id: str,
) -> Dict[str, Any]:
    """
    Get all insights for a specific client.

    This returns detailed recommendations for a single client,
    combining both the base recommendation engine and rules-based engine.
    """
    tenant_id = get_tenant_id(request)

    try:
        from cpa_panel.adapters import TaxReturnAdapter
        from calculator.recommendations import get_recommendations

        adapter = TaxReturnAdapter()
        tax_return = adapter.get_tax_return(session_id)

        if not tax_return:
            raise HTTPException(status_code=404, detail="Tax return not found")

        client_name = _extract_client_name(tax_return)
        insights = []
        total_savings = 0

        # Base recommendations
        try:
            result = get_recommendations(tax_return)
            for rec in result.recommendations:
                savings = rec.potential_savings or 0
                total_savings += savings

                insights.append({
                    "title": rec.title,
                    "description": rec.description,
                    "category": rec.category.value if hasattr(rec.category, 'value') else rec.category,
                    "priority": rec.priority.value if hasattr(rec.priority, 'value') else rec.priority,
                    "estimated_savings": savings,
                    "action_items": rec.action_items,
                    "source": "recommendation_engine",
                })
        except Exception as e:
            logger.warning(f"Error getting recommendations: {e}")

        # Rules-based insights
        try:
            from recommendation.rules_based_recommender import RulesBasedRecommender
            rules_recommender = RulesBasedRecommender()
            rule_insights = rules_recommender.analyze(tax_return)

            for insight in rule_insights:
                if not insight.applies:
                    continue

                savings = insight.estimated_impact or 0
                if savings > 0:
                    total_savings += savings

                insights.append({
                    "title": insight.title,
                    "description": insight.description,
                    "category": insight.category,
                    "priority": insight.priority,
                    "estimated_savings": savings,
                    "action_items": insight.action_items,
                    "irs_reference": insight.irs_reference,
                    "irs_form": insight.irs_form,
                    "rule_id": insight.rule_id,
                    "confidence": insight.confidence,
                    "source": "rules_engine",
                })
        except Exception as e:
            logger.warning(f"Error getting rules insights: {e}")

        # Sort by savings
        insights.sort(key=lambda x: x.get("estimated_savings", 0), reverse=True)

        return format_success_response({
            "session_id": session_id,
            "client_name": client_name,
            "total_savings_potential": float(money(total_savings)),
            "insights": insights,
            "insight_count": len(insights),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting client insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", dependencies=[Depends(require_internal_cpa_auth)])
async def get_insights_summary(
    request: Request,
) -> Dict[str, Any]:
    """
    Get high-level summary metrics for the CPA dashboard hero section.

    Returns:
    - Total savings identified across all clients
    - Number of actionable opportunities
    - Clients with high-priority alerts
    - Category breakdown totals
    """
    tenant_id = get_tenant_id(request)

    try:
        from src.database.session_persistence import get_session_persistence
        from cpa_panel.adapters import TaxReturnAdapter
        from calculator.recommendations import get_recommendations, RecommendationPriority

        persistence = get_session_persistence()
        sessions = persistence.list_sessions(tenant_id)

        adapter = TaxReturnAdapter()

        total_savings = 0
        total_opportunities = 0
        high_priority_count = 0
        clients_with_savings = 0

        category_totals = {
            "retirement": 0,
            "deductions": 0,
            "credits": 0,
            "investment": 0,
            "qbi": 0,
        }

        for session in sessions:
            session_id = session.session_id if hasattr(session, 'session_id') else session.get('session_id')
            if not session_id:
                continue

            tax_return = adapter.get_tax_return(session_id)
            if not tax_return:
                continue

            client_savings = 0

            try:
                result = get_recommendations(tax_return)
                for rec in result.recommendations:
                    savings = rec.potential_savings or 0
                    client_savings += savings
                    total_savings += savings
                    total_opportunities += 1

                    # Check priority
                    priority = rec.priority.value if hasattr(rec.priority, 'value') else rec.priority
                    if priority == "high":
                        high_priority_count += 1

                    # Categorize for dashboard breakdown
                    cat = rec.category.value if hasattr(rec.category, 'value') else rec.category
                    if "retirement" in cat.lower():
                        category_totals["retirement"] += savings
                    elif "deduction" in cat.lower():
                        category_totals["deductions"] += savings
                    elif "credit" in cat.lower():
                        category_totals["credits"] += savings
                    elif "investment" in cat.lower():
                        category_totals["investment"] += savings

                if client_savings > 0:
                    clients_with_savings += 1

            except Exception as e:
                logger.warning(f"Error processing {session_id}: {e}")

        return format_success_response({
            "total_savings_identified": float(money(total_savings)),
            "total_opportunities": total_opportunities,
            "high_priority_alerts": high_priority_count,
            "clients_with_savings": clients_with_savings,
            "total_clients": len(sessions),
            "category_breakdown": {
                "retirement": float(money(category_totals["retirement"])),
                "deductions": float(money(category_totals["deductions"])),
                "credits": float(money(category_totals["credits"])),
                "investment": float(money(category_totals["investment"])),
                "qbi": float(money(category_totals["qbi"])),
            },
        })

    except Exception as e:
        logger.error(f"Error getting insights summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _extract_client_name(tax_return) -> str:
    """Extract client name from tax return."""
    taxpayer = getattr(tax_return, 'taxpayer', None)
    if taxpayer:
        first = getattr(taxpayer, 'first_name', '') or ''
        last = getattr(taxpayer, 'last_name', '') or ''
        name = f"{first} {last}".strip()
        if name:
            return name
    return "Unknown Client"


def _calculate_category_breakdown(insights: List[Dict]) -> Dict[str, Any]:
    """Calculate category breakdown from insights list."""
    breakdown = {}

    for insight in insights:
        cat = insight.get("category", "other")
        if cat not in breakdown:
            breakdown[cat] = {
                "count": 0,
                "total_savings": 0,
            }

        breakdown[cat]["count"] += 1
        breakdown[cat]["total_savings"] += insight.get("estimated_savings", 0)

    # Round totals
    for cat in breakdown:
        breakdown[cat]["total_savings"] = float(money(breakdown[cat]["total_savings"]))

    return breakdown
