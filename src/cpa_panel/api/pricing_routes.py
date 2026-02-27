"""
CPA Panel Pricing Routes

API endpoints for complexity-based pricing calculation and
engagement quote generation.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import logging

logger = logging.getLogger(__name__)

pricing_router = APIRouter(tags=["Pricing"])


def get_pricing_engine():
    """Get the pricing engine instance."""
    from cpa_panel.pricing.complexity_pricing import EngagementPricingEngine
    return EngagementPricingEngine()


def get_tax_return(session_id: str):
    """Get tax return from session."""
    try:
        from cpa_panel.adapters import TaxReturnAdapter
        adapter = TaxReturnAdapter()
        return adapter.get_tax_return(session_id)
    except Exception as e:
        return None


# =============================================================================
# PRICING CALCULATION
# =============================================================================

@pricing_router.post("/session/{session_id}/pricing/calculate")
async def calculate_pricing(session_id: str, request: Request):
    """
    Calculate pricing guidance based on tax return complexity.

    Analyzes the client's tax return to determine:
    - Complexity tier (Simple to Enterprise)
    - Estimated hours
    - Suggested price range
    - Detected complexity factors
    - Value justification

    DISCLAIMER: Pricing is advisory only. Final pricing
    decisions are at the CPA's discretion.
    """
    tax_return = get_tax_return(session_id)
    if not tax_return:
        raise HTTPException(status_code=404, detail=f"Tax return not found: {session_id}")

    try:
        # Convert tax return to pricing data format
        pricing_data = _extract_pricing_data(tax_return)

        engine = get_pricing_engine()
        guidance = engine.get_pricing_guidance(pricing_data)

        return JSONResponse({
            "success": True,
            "session_id": session_id,
            **guidance,
        })

    except Exception as e:
        logger.error(f"Pricing calculation error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@pricing_router.get("/pricing/tiers")
async def get_pricing_tiers(request: Request):
    """
    Get all pricing tier information.

    Returns reference information for all complexity tiers:
    - Tier descriptions
    - Typical forms
    - Complexity indicators
    - Price ranges
    - Value justification

    Useful for understanding the pricing model and
    for manual tier selection.
    """
    try:
        engine = get_pricing_engine()
        tiers = engine.get_all_tiers()

        return JSONResponse({
            "success": True,
            **tiers,
        })

    except Exception as e:
        logger.error(f"Get pricing tiers error: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


@pricing_router.post("/session/{session_id}/pricing/quote")
async def generate_quote(session_id: str, request: Request):
    """
    Generate a pricing quote for engagement letter.

    Request body (optional):
        - tier_override: Override the auto-detected tier
        - price_override: Override the calculated price
        - discount_percent: Apply a discount percentage
        - services: List of additional services to include
        - notes: Custom notes for the quote

    Returns a structured quote ready for engagement letter.
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.debug(f"Failed to parse request body: {e}")
        body = {}

    tax_return = get_tax_return(session_id)
    if not tax_return:
        raise HTTPException(status_code=404, detail=f"Tax return not found: {session_id}")

    try:
        # Get base pricing
        pricing_data = _extract_pricing_data(tax_return)
        engine = get_pricing_engine()
        guidance = engine.get_pricing_guidance(pricing_data)

        # Apply overrides
        tier = body.get("tier_override") or guidance["assessed_tier"]
        base_price = body.get("price_override") or guidance["suggested_price_range"]["max"]
        discount_percent = body.get("discount_percent", 0)
        services = body.get("services", [])
        notes = body.get("notes", "")

        # Calculate final price
        discount_amount = base_price * (discount_percent / 100)
        final_price = base_price - discount_amount

        # Add services
        service_total = 0
        service_items = []
        for service in services:
            service_price = service.get("price", 0)
            service_total += service_price
            service_items.append({
                "name": service.get("name", "Additional Service"),
                "price": service_price,
            })

        total_price = final_price + service_total

        # Client info
        client_name = "Client"
        if tax_return.taxpayer:
            first = tax_return.taxpayer.first_name or ""
            last = tax_return.taxpayer.last_name or ""
            client_name = f"{first} {last}".strip() or "Client"

        quote = {
            "quote_id": f"Q-{session_id[:8].upper()}",
            "session_id": session_id,
            "client_name": client_name,
            "complexity_tier": tier,
            "tier_name": guidance["tier_name"],
            "detected_factors": guidance["detected_factors"],
            "estimated_hours": guidance["estimated_hours"],
            "pricing": {
                "base_price": base_price,
                "discount_percent": discount_percent,
                "discount_amount": discount_amount,
                "services": service_items,
                "services_total": service_total,
                "final_price": total_price,
                "currency": "USD",
            },
            "value_justification": guidance["value_justification"],
            "notes": notes,
            "disclaimer": guidance["disclaimer"],
            "valid_days": 30,
        }

        return JSONResponse({
            "success": True,
            "quote": quote,
        })

    except Exception as e:
        logger.error(f"Generate quote error for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred")


def _extract_pricing_data(tax_return) -> dict:
    """Extract pricing-relevant data from tax return."""
    data = {
        "adjusted_gross_income": tax_return.adjusted_gross_income or 0,
    }

    income = tax_return.income
    if income:
        data["self_employment_income"] = getattr(income, "self_employment_income", 0) or 0
        data["rental_income"] = getattr(income, "rental_income", 0) or 0

        # Check for Schedule C
        if data["self_employment_income"] > 0:
            data["schedule_c"] = True

        # Check for Schedule E
        if data["rental_income"] > 0:
            data["schedule_e"] = True

        # Check for investments
        cap_gains = getattr(income, "long_term_capital_gains", 0) or 0
        cap_gains += getattr(income, "short_term_capital_gains", 0) or 0
        if cap_gains != 0:
            data["capital_gains"] = cap_gains
            data["schedule_d"] = True

    # K-1s would need separate tracking
    data["schedule_k1s"] = []

    # Multi-state would need separate tracking
    data["state_returns"] = []

    return data
