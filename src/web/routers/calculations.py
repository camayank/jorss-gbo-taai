"""
Calculations Routes - Tax Calculations and Optimization

SPEC-005: Extracted from app.py for modularity.

Routes:
- POST /api/calculate/complete - Full tax calculation
- POST /api/calculate-tax - Quick tax calculation
- POST /api/estimate - Tax estimate
- POST /api/optimize - General optimization
- POST /api/optimize/filing-status - Filing status optimization
- POST /api/optimize/credits - Credits optimization
- POST /api/optimize/deductions - Deductions optimization
- GET /api/recommendations - Get tax recommendations
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import logging
from decimal import Decimal
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Calculations"])

# Dependencies will be injected
_calculator = None


def set_dependencies(calculator):
    """Set dependencies from the main app."""
    global _calculator
    _calculator = calculator


def _get_calculator():
    """Get tax calculator instance."""
    global _calculator
    if _calculator is None:
        from calculator.tax_calculator import TaxCalculator
        _calculator = TaxCalculator()
    return _calculator


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert value to Decimal."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return default


# =============================================================================
# CALCULATION ROUTES
# =============================================================================

@router.post("/calculate/complete")
async def calculate_complete(request: Request):
    """
    Perform a complete tax calculation with all components.

    Includes: AGI, deductions, credits, tax liability, refund/owed.
    """
    try:
        body = await request.json()
        tax_year = body.get("tax_year", 2025)

        calculator = _get_calculator()

        # Extract taxpayer info
        taxpayer = body.get("taxpayer", {})
        income = body.get("income", {})
        deductions = body.get("deductions", {})
        credits = body.get("credits", {})
        withholdings = body.get("withholdings", {})

        # Calculate gross income
        wages = _safe_float(income.get("wages", 0))
        interest = _safe_float(income.get("interest_income", 0))
        dividends = _safe_float(income.get("dividend_income", 0))
        capital_gains = _safe_float(income.get("capital_gains", 0))
        business_income = _safe_float(income.get("business_income", 0))
        rental_income = _safe_float(income.get("rental_income", 0))
        other_income = _safe_float(income.get("other_income", 0))

        gross_income = (wages + interest + dividends + capital_gains +
                       business_income + rental_income + other_income)

        # Calculate adjustments
        adjustments = _safe_float(income.get("adjustments", 0))
        agi = gross_income - adjustments

        # Calculate deductions
        filing_status = taxpayer.get("filing_status", "single")
        standard_deduction = calculator.get_standard_deduction(filing_status, tax_year)
        itemized_total = _safe_float(deductions.get("itemized_total", 0))

        use_itemized = itemized_total > standard_deduction
        total_deductions = itemized_total if use_itemized else standard_deduction

        # Calculate taxable income
        taxable_income = max(0, agi - total_deductions)

        # Calculate tax
        tax_liability = calculator.calculate_tax(
            taxable_income=taxable_income,
            filing_status=filing_status,
            tax_year=tax_year,
        )

        # Apply credits
        total_credits = _safe_float(credits.get("total", 0))
        tax_after_credits = max(0, tax_liability - total_credits)

        # Calculate withholdings
        federal_withheld = _safe_float(withholdings.get("federal_withheld", 0))
        estimated_payments = _safe_float(withholdings.get("estimated_payments", 0))
        total_payments = federal_withheld + estimated_payments

        # Calculate refund or owed
        refund_or_owed = total_payments - tax_after_credits

        # Effective tax rate
        effective_rate = (tax_after_credits / agi * 100) if agi > 0 else 0

        result = {
            "status": "success",
            "tax_year": tax_year,
            "filing_status": filing_status,
            "income": {
                "gross_income": float(money(gross_income)),
                "adjustments": float(money(adjustments)),
                "agi": float(money(agi)),
            },
            "deductions": {
                "standard_deduction": float(money(standard_deduction)),
                "itemized_deduction": float(money(itemized_total)),
                "deduction_used": "itemized" if use_itemized else "standard",
                "total_deductions": float(money(total_deductions)),
            },
            "tax": {
                "taxable_income": float(money(taxable_income)),
                "tax_liability": float(money(tax_liability)),
                "total_credits": float(money(total_credits)),
                "tax_after_credits": float(money(tax_after_credits)),
            },
            "payments": {
                "federal_withheld": float(money(federal_withheld)),
                "estimated_payments": float(money(estimated_payments)),
                "total_payments": float(money(total_payments)),
            },
            "result": {
                "refund_or_owed": float(money(refund_or_owed)),
                "effective_tax_rate": float(money(effective_rate)),
                "is_refund": refund_or_owed >= 0,
            },
        }

        return JSONResponse(result)

    except Exception as e:
        logger.exception(f"Complete calculation error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/calculate-tax")
async def calculate_tax_quick(request: Request):
    """
    Quick tax calculation for chatbot/interactive use.

    Accepts simplified inputs and returns tax estimate.
    """
    try:
        body = await request.json()

        # Extract inputs (support multiple field names)
        income = _safe_float(body.get("income") or body.get("gross_income") or body.get("wages", 0))
        filing_status = body.get("filing_status", "single")
        tax_year = body.get("tax_year", 2025)
        deductions = _safe_float(body.get("deductions", 0))
        withholdings = _safe_float(body.get("withholdings") or body.get("federal_withheld", 0))

        calculator = _get_calculator()

        # Get standard deduction
        standard_deduction = calculator.get_standard_deduction(filing_status, tax_year)

        # Use larger of standard or itemized
        total_deductions = max(standard_deduction, deductions)

        # Calculate taxable income
        taxable_income = max(0, income - total_deductions)

        # Calculate tax
        tax_liability = calculator.calculate_tax(
            taxable_income=taxable_income,
            filing_status=filing_status,
            tax_year=tax_year,
        )

        # Calculate refund/owed
        refund_or_owed = withholdings - tax_liability

        return JSONResponse({
            "status": "success",
            "input": {
                "income": income,
                "filing_status": filing_status,
                "tax_year": tax_year,
            },
            "calculation": {
                "standard_deduction": float(money(standard_deduction)),
                "deductions_used": float(money(total_deductions)),
                "taxable_income": float(money(taxable_income)),
                "tax_liability": float(money(tax_liability)),
                "withholdings": float(money(withholdings)),
                "refund_or_owed": float(money(refund_or_owed)),
            },
            "is_refund": refund_or_owed >= 0,
        })

    except Exception as e:
        logger.exception(f"Quick calculation error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/estimate")
async def estimate_tax(request: Request):
    """
    Tax estimate for lead capture and chatbot.

    Simplified calculation for quick estimates using OnboardingBenefitEstimator.
    """
    try:
        body = await request.json()

        # Support multiple income field names
        wages = _safe_float(body.get("wages") or body.get("income") or body.get("annual_income", 0))
        withholding = _safe_float(body.get("withholding", 0))
        filing_status = body.get("filing_status", "single")
        num_dependents = int(body.get("num_dependents", 0))
        state_code = body.get("state_code")

        # Use the benefit estimator for accurate calculations
        from onboarding.benefit_estimator import OnboardingBenefitEstimator

        estimator = OnboardingBenefitEstimator()
        estimate = estimator.estimate_from_basics(
            wages=wages,
            withholding=withholding,
            filing_status=filing_status,
            num_dependents=num_dependents,
            state_code=state_code,
        )

        return JSONResponse({
            "status": "success",
            "federal_tax": float(money(estimate.federal_tax)),
            "state_tax": float(money(estimate.state_tax)),
            "effective_rate": round(estimate.effective_rate, 1),
            "marginal_rate": round(estimate.marginal_rate, 0),
            "estimated_refund": float(money(estimate.estimated_refund)),
            "estimated_owed": float(money(estimate.estimated_owed)),
            "is_refund": estimate.is_refund,
            "confidence": estimate.confidence,
            "estimate": {
                "income": wages,
                "filing_status": filing_status,
                "federal_tax": float(money(estimate.federal_tax)),
                "effective_rate": round(estimate.effective_rate, 1),
            },
            "disclaimer": "This is an estimate only. Actual tax may vary based on complete tax situation.",
        })

    except Exception as e:
        logger.exception(f"Estimate error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


# =============================================================================
# OPTIMIZATION ROUTES
# =============================================================================

@router.post("/optimize")
async def optimize_general(request: Request):
    """General tax optimization suggestions."""
    try:
        body = await request.json()

        from calculator.recommendations import get_recommendations

        recommendations = get_recommendations(body)

        return JSONResponse({
            "status": "success",
            "recommendations": recommendations.recommendations if hasattr(recommendations, 'recommendations') else recommendations,
            "count": len(recommendations.recommendations) if hasattr(recommendations, 'recommendations') else len(recommendations),
        })

    except Exception as e:
        logger.exception(f"Optimize error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/optimize/filing-status")
async def optimize_filing_status(request: Request):
    """Analyze optimal filing status."""
    try:
        body = await request.json()

        calculator = _get_calculator()

        income = _safe_float(body.get("income", 0))
        married = body.get("married", False)
        spouse_income = _safe_float(body.get("spouse_income", 0))

        results = []

        if married:
            # Compare MFJ vs MFS
            statuses = ["married_filing_jointly", "married_filing_separately"]
            combined_income = income + spouse_income

            for status in statuses:
                if status == "married_filing_jointly":
                    std_ded = calculator.get_standard_deduction(status, 2025)
                    taxable = max(0, combined_income - std_ded)
                    tax = calculator.calculate_tax(taxable, status, 2025)
                else:
                    # MFS - calculate for each spouse
                    std_ded = calculator.get_standard_deduction(status, 2025)
                    taxable1 = max(0, income - std_ded)
                    taxable2 = max(0, spouse_income - std_ded)
                    tax = (calculator.calculate_tax(taxable1, status, 2025) +
                           calculator.calculate_tax(taxable2, status, 2025))

                results.append({
                    "filing_status": status,
                    "estimated_tax": float(money(tax)),
                })
        else:
            # Single or HOH
            statuses = ["single", "head_of_household"]
            for status in statuses:
                std_ded = calculator.get_standard_deduction(status, 2025)
                taxable = max(0, income - std_ded)
                tax = calculator.calculate_tax(taxable, status, 2025)

                results.append({
                    "filing_status": status,
                    "estimated_tax": float(money(tax)),
                })

        # Find best option
        best = min(results, key=lambda x: x["estimated_tax"])

        return JSONResponse({
            "status": "success",
            "analysis": results,
            "recommended": best["filing_status"],
            "potential_savings": float(money(max(r["estimated_tax"] for r in results) - best["estimated_tax"])),
        })

    except Exception as e:
        logger.exception(f"Filing status optimization error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/optimize/credits")
async def optimize_credits(request: Request):
    """Analyze available tax credits."""
    try:
        body = await request.json()

        income = _safe_float(body.get("income", 0))
        filing_status = body.get("filing_status", "single")
        dependents = body.get("dependents", [])
        education_expenses = _safe_float(body.get("education_expenses", 0))
        childcare_expenses = _safe_float(body.get("childcare_expenses", 0))

        credits_available = []

        # Child Tax Credit
        num_children = len([d for d in dependents if d.get("age", 0) < 17])
        if num_children > 0:
            ctc_amount = num_children * 2000  # 2025 amount
            credits_available.append({
                "credit": "Child Tax Credit",
                "amount": ctc_amount,
                "description": f"${2000} per qualifying child under 17",
            })

        # Child and Dependent Care Credit
        if childcare_expenses > 0 and num_children > 0:
            max_expenses = 3000 if num_children == 1 else 6000
            credit_rate = 0.20  # Simplified
            cdcc_amount = min(childcare_expenses, max_expenses) * credit_rate
            credits_available.append({
                "credit": "Child and Dependent Care Credit",
                "amount": float(money(cdcc_amount)),
                "description": "Credit for childcare expenses while working",
            })

        # Education Credits
        if education_expenses > 0:
            # American Opportunity Credit
            aoc_amount = min(education_expenses, 2500)
            credits_available.append({
                "credit": "American Opportunity Credit",
                "amount": float(money(aoc_amount)),
                "description": "Up to $2,500 for first 4 years of college",
            })

        # Earned Income Credit (simplified)
        if income < 60000 and num_children > 0:
            credits_available.append({
                "credit": "Earned Income Tax Credit",
                "amount": "Varies",
                "description": "Refundable credit for low-to-moderate income",
            })

        total_potential = sum(c["amount"] for c in credits_available if isinstance(c["amount"], (int, float)))

        return JSONResponse({
            "status": "success",
            "credits_available": credits_available,
            "total_potential_credits": float(money(total_potential)),
            "note": "Actual credit amounts depend on income limits and eligibility",
        })

    except Exception as e:
        logger.exception(f"Credits optimization error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.post("/optimize/deductions")
async def optimize_deductions(request: Request):
    """Analyze deduction optimization opportunities."""
    try:
        body = await request.json()

        filing_status = body.get("filing_status", "single")
        deductions = body.get("deductions", {})

        calculator = _get_calculator()
        standard_deduction = calculator.get_standard_deduction(filing_status, 2025)

        # Calculate itemized total
        mortgage_interest = _safe_float(deductions.get("mortgage_interest", 0))
        state_local_taxes = min(_safe_float(deductions.get("state_local_taxes", 0)), 10000)  # SALT cap
        charitable = _safe_float(deductions.get("charitable", 0))
        medical = _safe_float(deductions.get("medical", 0))
        other = _safe_float(deductions.get("other", 0))

        itemized_total = mortgage_interest + state_local_taxes + charitable + medical + other

        recommendations = []

        if itemized_total > standard_deduction:
            recommendations.append({
                "recommendation": "Itemize deductions",
                "savings": float(money(itemized_total - standard_deduction)),
                "description": "Your itemized deductions exceed the standard deduction",
            })
        else:
            shortfall = standard_deduction - itemized_total
            recommendations.append({
                "recommendation": "Take standard deduction",
                "savings": float(money(standard_deduction - itemized_total)) if itemized_total > 0 else 0,
                "description": f"Standard deduction saves more. Shortfall: ${shortfall:,.0f}",
            })

            # Bunching suggestion
            if itemized_total > standard_deduction * 0.7:
                recommendations.append({
                    "recommendation": "Consider bunching strategy",
                    "description": "Combine 2 years of deductions into 1 year to exceed standard deduction",
                })

        return JSONResponse({
            "status": "success",
            "analysis": {
                "standard_deduction": float(money(standard_deduction)),
                "itemized_total": float(money(itemized_total)),
                "recommended": "itemized" if itemized_total > standard_deduction else "standard",
            },
            "breakdown": {
                "mortgage_interest": float(money(mortgage_interest)),
                "state_local_taxes": float(money(state_local_taxes)),
                "charitable": float(money(charitable)),
                "medical": float(money(medical)),
                "other": float(money(other)),
            },
            "recommendations": recommendations,
        })

    except Exception as e:
        logger.exception(f"Deductions optimization error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/recommendations")
async def get_recommendations_route(request: Request):
    """Get tax optimization recommendations for current session."""
    try:
        session_id = request.query_params.get("session_id") or request.cookies.get("tax_session_id")

        if not session_id:
            return JSONResponse({
                "status": "success",
                "recommendations": [],
                "message": "No session found",
            })

        # Load session data
        from database.session_persistence import get_session_persistence
        persistence = get_session_persistence()
        return_data = persistence.load_session_tax_return(session_id)

        if not return_data:
            return JSONResponse({
                "status": "success",
                "recommendations": [],
                "message": "No return data found",
            })

        # Get recommendations
        from calculator.recommendations import get_recommendations
        recommendations = get_recommendations(return_data.get("return_data", {}))

        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "recommendations": recommendations.recommendations if hasattr(recommendations, 'recommendations') else recommendations,
        })

    except Exception as e:
        logger.exception(f"Get recommendations error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )
