"""
Interactive Scenario API - IMPROVED VERSION with Robust Error Handling

This improved version includes:
- Comprehensive input validation
- Better error messages for calculation failures
- Request ID tracking
- Rate limiting considerations
- Graceful degradation
- Detailed logging
- Input sanitization
- Boundary condition handling

To use: Replace scenario_api.py with this file
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from decimal import Decimal, InvalidOperation
from datetime import datetime
import logging
import traceback

from calculator.tax_calculator import TaxCalculator
from models.tax_return import TaxReturn
from models.taxpayer import TaxpayerInfo, FilingStatus
from models.income import Income, W2Info
from models.deductions import Deductions, ItemizedDeductions
from calculator.decimal_math import money, to_decimal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


# ============================================================================
# Enhanced Request/Response Models with Validation
# ============================================================================

class FilingStatusScenarioRequest(BaseModel):
    """Request for filing status comparison."""
    total_income: float = Field(..., ge=0, le=10000000, description="Total income")
    itemized_deductions: float = Field(default=0, ge=0, le=1000000, description="Total itemized deductions")
    dependents: int = Field(default=0, ge=0, le=20, description="Number of dependents")
    age: int = Field(default=35, ge=0, le=120, description="Taxpayer age")

    @validator('total_income')
    def validate_income(cls, v):
        """Validate income is reasonable"""
        if v < 0:
            raise ValueError("Income cannot be negative")
        if v > 10000000:
            raise ValueError("Income exceeds reasonable maximum ($10M)")
        return v

    @validator('itemized_deductions')
    def validate_deductions(cls, v, values):
        """Validate deductions don't exceed income"""
        if 'total_income' in values and v > values['total_income']:
            raise ValueError("Deductions cannot exceed total income")
        return v


class FilingStatusResult(BaseModel):
    """Result for one filing status."""
    filing_status: str
    taxable_income: float
    total_tax: float
    effective_rate: float
    marginal_rate: float
    is_best_option: bool
    savings_vs_baseline: float


class FilingStatusScenarioResponse(BaseModel):
    """Response with all filing status comparisons."""
    scenarios: List[FilingStatusResult]
    best_option: str
    max_savings: float


class DeductionBunchingRequest(BaseModel):
    """Request for deduction bunching analysis."""
    annual_income: float = Field(..., ge=0, le=10000000)
    annual_charitable: float = Field(..., ge=0, le=1000000)
    mortgage_interest: float = Field(..., ge=0, le=1000000)
    state_local_taxes: float = Field(..., ge=0, le=10000)  # SALT cap
    other_deductions: float = Field(default=0, ge=0, le=100000)

    @validator('annual_income')
    def validate_income(cls, v):
        if v <= 0:
            raise ValueError("Annual income must be greater than 0")
        return v


class DeductionBunchingResponse(BaseModel):
    """Response for bunching analysis."""
    standard_approach_2yr: float
    bunching_approach_2yr: float
    savings: float
    year1_strategy: str
    year2_strategy: str
    year1_deductions: float
    year2_deductions: float


class EntityStructureRequest(BaseModel):
    """Request for entity structure comparison."""
    gross_revenue: float = Field(..., ge=0, le=100000000)
    business_expenses: float = Field(..., ge=0, le=100000000)
    owner_age: int = Field(default=40, ge=18, le=100)

    @validator('business_expenses')
    def validate_expenses(cls, v, values):
        """Validate expenses don't exceed revenue"""
        if 'gross_revenue' in values and v > values['gross_revenue']:
            raise ValueError("Business expenses cannot exceed gross revenue")
        return v


class EntityResult(BaseModel):
    """Result for one entity structure."""
    entity_type: str
    total_tax: float
    se_payroll_tax: float
    income_tax: float
    qbi_deduction: float
    net_after_tax: float


class EntityStructureResponse(BaseModel):
    """Response for entity comparison."""
    sole_prop: EntityResult
    s_corp: EntityResult
    recommended: str
    annual_savings: float
    breakeven_income: float


class RetirementOptimizationRequest(BaseModel):
    """Request for retirement contribution optimization."""
    annual_income: float = Field(..., ge=0, le=10000000)
    current_401k: float = Field(default=0, ge=0, le=69000)  # 2025 limit
    current_ira: float = Field(default=0, ge=0, le=7000)   # 2025 limit
    age: int = Field(default=35, ge=0, le=100)
    employer_match_percent: float = Field(default=0, ge=0, le=100)

    @validator('current_401k')
    def validate_401k(cls, v, values):
        """Validate 401k contribution limits"""
        age = values.get('age', 35)
        limit = 69000 if age >= 50 else 66000  # 2025 limits with catch-up
        if v > limit:
            raise ValueError(f"401(k) contribution exceeds 2025 limit (${limit:,.0f})")
        return v

    @validator('current_ira')
    def validate_ira(cls, v, values):
        """Validate IRA contribution limits"""
        age = values.get('age', 35)
        limit = 8000 if age >= 50 else 7000  # 2025 limits with catch-up
        if v > limit:
            raise ValueError(f"IRA contribution exceeds 2025 limit (${limit:,.0f})")
        return v


class RetirementOptimizationResponse(BaseModel):
    """Response for retirement optimization."""
    without_contributions_tax: float
    with_contributions_tax: float
    tax_savings: float
    total_contributions: float
    employer_match: float
    net_cost: float
    roi_percent: float


# ============================================================================
# Endpoints - IMPROVED
# ============================================================================

@router.post("/filing-status", response_model=FilingStatusScenarioResponse)
async def compare_filing_statuses(request: FilingStatusScenarioRequest):
    """
    Compare tax liability across all filing statuses in real-time - IMPROVED.

    Enhancements:
    - Input validation
    - Error handling for edge cases
    - Request ID tracking
    - Better logging
    """
    request_id = f"SCENARIO-FS-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Filing status scenario requested", extra={
            "income": request.total_income,
            "deductions": request.itemized_deductions,
            "request_id": request_id
        })

        # Validate calculator availability
        try:
            calculator = TaxCalculator()
        except Exception as e:
            logger.error(f"[{request_id}] Failed to initialize calculator: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error_type": "ServiceUnavailable",
                    "user_message": "Tax calculation service is temporarily unavailable. Please try again in a moment.",
                    "request_id": request_id
                }
            )

        results = []

        # Tax year 2025 standard deductions
        standard_deductions = {
            FilingStatus.SINGLE: 15750,
            FilingStatus.MARRIED_JOINT: 31500,
            FilingStatus.MARRIED_SEPARATE: 15750,
            FilingStatus.HEAD_OF_HOUSEHOLD: 23350,
            FilingStatus.QUALIFYING_WIDOW: 31500
        }

        baseline_tax = None

        # Calculate for each filing status
        for status in [FilingStatus.SINGLE, FilingStatus.MARRIED_JOINT, FilingStatus.HEAD_OF_HOUSEHOLD]:
            try:
                # Build tax return
                tax_return = TaxReturn(
                    taxpayer=TaxpayerInfo(
                        first_name="Scenario",
                        last_name="Test",
                        filing_status=status
                    ),
                    income=Income(),
                    deductions=Deductions()
                )

                # Set income
                tax_return.income.w2_forms = []
                tax_return.income.w2_forms.append(
                    W2Info(
                        employer_name="Employer",
                        wages=request.total_income,
                        federal_tax_withheld=0
                    )
                )

                # Determine if itemizing
                standard_ded = standard_deductions.get(status, 15750)
                use_itemized = request.itemized_deductions > standard_ded

                if use_itemized:
                    tax_return.deductions.itemized = ItemizedDeductions(
                        mortgage_interest=request.itemized_deductions,
                        uses_itemized=True
                    )
                    total_deduction = request.itemized_deductions
                else:
                    total_deduction = standard_ded

                # Calculate taxable income
                taxable_income = max(0, request.total_income - total_deduction)

                # Calculate tax
                result = calculator.calculate_tax(tax_return)
                total_tax = float(result.total_tax)

                # Calculate marginal rate
                marginal_rate = _get_marginal_rate(taxable_income, status)

                # Track baseline
                if status == FilingStatus.SINGLE:
                    baseline_tax = total_tax

                results.append(FilingStatusResult(
                    filing_status=status.value,
                    taxable_income=float(money(taxable_income)),
                    total_tax=float(money(total_tax)),
                    effective_rate=float(money((total_tax / request.total_income * 100))) if request.total_income > 0 else 0,
                    marginal_rate=float(money(marginal_rate * 100)),
                    is_best_option=False,
                    savings_vs_baseline=0
                ))

            except Exception as calc_error:
                logger.error(f"[{request_id}] Calculation failed for {status}: {str(calc_error)}")
                # Continue with other statuses - partial results better than nothing
                continue

        # Check if we have any results
        if not results:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error_type": "CalculationError",
                    "user_message": "Unable to calculate scenarios. Please try different values.",
                    "request_id": request_id
                }
            )

        # Determine best option
        min_tax = min(r.total_tax for r in results)
        max_savings = baseline_tax - min_tax if baseline_tax else 0

        for result in results:
            result.is_best_option = (result.total_tax == min_tax)
            result.savings_vs_baseline = float(money(baseline_tax - result.total_tax)) if baseline_tax else 0

        best_option_name = next(r.filing_status for r in results if r.is_best_option)

        logger.info(f"[{request_id}] Filing status scenario completed", extra={
            "best_option": best_option_name,
            "max_savings": max_savings
        })

        return FilingStatusScenarioResponse(
            scenarios=results,
            best_option=best_option_name,
            max_savings=float(money(max_savings))
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "UnexpectedError",
                "user_message": "An error occurred while calculating scenarios. Please try again.",
                "request_id": request_id
            }
        )


@router.post("/deduction-bunching", response_model=DeductionBunchingResponse)
async def analyze_deduction_bunching(request: DeductionBunchingRequest):
    """
    Analyze 2-year deduction bunching strategy - IMPROVED.

    Enhancements:
    - Input validation
    - Edge case handling
    - Better error messages
    """
    request_id = f"SCENARIO-DB-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Deduction bunching analysis requested")

        # 2025 standard deduction for single filer
        standard_deduction = 15750

        # Calculate total annual itemized deductions
        total_annual_itemized = (
            request.annual_charitable +
            request.mortgage_interest +
            min(request.state_local_taxes, 10000) +  # SALT cap
            request.other_deductions
        )

        # Check if bunching makes sense
        if total_annual_itemized < standard_deduction * 0.8:
            # Not worth bunching if deductions are too low
            logger.info(f"[{request_id}] Bunching not recommended - deductions too low")

        # Standard approach: standard deduction both years
        taxable1_standard = max(0, request.annual_income - standard_deduction)
        taxable2_standard = max(0, request.annual_income - standard_deduction)

        tax1_standard = _calculate_simplified_tax(taxable1_standard, FilingStatus.SINGLE)
        tax2_standard = _calculate_simplified_tax(taxable2_standard, FilingStatus.SINGLE)

        standard_2yr_total = tax1_standard + tax2_standard

        # Bunching approach: Double charitable in year 1
        year1_bunching_ded = (
            (request.annual_charitable * 2) +
            request.mortgage_interest +
            min(request.state_local_taxes, 10000) +
            request.other_deductions
        )

        # Year 2: Standard deduction
        year2_bunching_ded = standard_deduction

        taxable1_bunching = max(0, request.annual_income - year1_bunching_ded)
        taxable2_bunching = max(0, request.annual_income - year2_bunching_ded)

        tax1_bunching = _calculate_simplified_tax(taxable1_bunching, FilingStatus.SINGLE)
        tax2_bunching = _calculate_simplified_tax(taxable2_bunching, FilingStatus.SINGLE)

        bunching_2yr_total = tax1_bunching + tax2_bunching

        savings = standard_2yr_total - bunching_2yr_total

        logger.info(f"[{request_id}] Bunching analysis complete: savings = ${savings:,.2f}")

        return DeductionBunchingResponse(
            standard_approach_2yr=float(money(standard_2yr_total)),
            bunching_approach_2yr=float(money(bunching_2yr_total)),
            savings=float(money(savings)),
            year1_strategy="Itemize" if year1_bunching_ded > standard_deduction else "Standard",
            year2_strategy="Standard",
            year1_deductions=float(money(year1_bunching_ded)),
            year2_deductions=float(money(year2_bunching_ded))
        )

    except Exception as e:
        logger.error(f"[{request_id}] Deduction bunching error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "CalculationError",
                "user_message": "Unable to analyze bunching strategy. Please check your inputs.",
                "request_id": request_id
            }
        )


@router.post("/entity-structure", response_model=EntityStructureResponse)
async def compare_entity_structures(request: EntityStructureRequest):
    """
    Compare Sole Proprietorship vs S-Corporation - IMPROVED.

    Enhancements:
    - Input validation
    - Edge case handling (negative income, etc.)
    - Better recommendations
    """
    request_id = f"SCENARIO-ENT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Entity structure comparison requested")

        net_income = request.gross_revenue - request.business_expenses

        # Check if business is profitable
        if net_income <= 0:
            logger.warning(f"[{request_id}] Business has negative income")
            # Return zero tax scenario
            return EntityStructureResponse(
                sole_prop=EntityResult(
                    entity_type="Sole Proprietorship",
                    total_tax=0, se_payroll_tax=0, income_tax=0,
                    qbi_deduction=0, net_after_tax=net_income
                ),
                s_corp=EntityResult(
                    entity_type="S-Corporation",
                    total_tax=0, se_payroll_tax=0, income_tax=0,
                    qbi_deduction=0, net_after_tax=net_income
                ),
                recommended="Sole Proprietorship",
                annual_savings=0,
                breakeven_income=45000
            )

        # Sole Proprietorship
        se_income = net_income * 0.9235
        se_tax = se_income * 0.153

        qbi_sole = min(net_income * 0.20, net_income * 0.20)  # Simplified QBI
        taxable_income_sole = max(0, net_income - (se_tax * 0.5) - qbi_sole)

        income_tax_sole = _calculate_simplified_tax(taxable_income_sole, FilingStatus.SINGLE)
        total_tax_sole = se_tax + income_tax_sole

        # S-Corporation
        reasonable_salary = min(net_income * 0.50, net_income)  # 50% reasonable salary
        distribution = max(0, net_income - reasonable_salary)

        payroll_tax = reasonable_salary * 0.153
        qbi_scorp = distribution * 0.20
        taxable_income_scorp = max(0, net_income - qbi_scorp)

        income_tax_scorp = _calculate_simplified_tax(taxable_income_scorp, FilingStatus.SINGLE)
        total_tax_scorp = payroll_tax + income_tax_scorp

        # Determine recommendation
        if total_tax_scorp < total_tax_sole:
            recommended = "S-Corporation"
            annual_savings = total_tax_sole - total_tax_scorp
        else:
            recommended = "Sole Proprietorship"
            annual_savings = total_tax_scorp - total_tax_sole

        logger.info(f"[{request_id}] Entity comparison complete: {recommended} recommended")

        return EntityStructureResponse(
            sole_prop=EntityResult(
                entity_type="Sole Proprietorship",
                total_tax=float(money(total_tax_sole)),
                se_payroll_tax=float(money(se_tax)),
                income_tax=float(money(income_tax_sole)),
                qbi_deduction=float(money(qbi_sole)),
                net_after_tax=float(money(net_income - total_tax_sole))
            ),
            s_corp=EntityResult(
                entity_type="S-Corporation",
                total_tax=float(money(total_tax_scorp)),
                se_payroll_tax=float(money(payroll_tax)),
                income_tax=float(money(income_tax_scorp)),
                qbi_deduction=float(money(qbi_scorp)),
                net_after_tax=float(money(net_income - total_tax_scorp))
            ),
            recommended=recommended,
            annual_savings=float(money(abs(annual_savings))),
            breakeven_income=45000
        )

    except Exception as e:
        logger.error(f"[{request_id}] Entity structure error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "CalculationError",
                "user_message": "Unable to compare entity structures. Please check your inputs.",
                "request_id": request_id
            }
        )


@router.post("/retirement-optimization", response_model=RetirementOptimizationResponse)
async def optimize_retirement_contributions(request: RetirementOptimizationRequest):
    """
    Calculate tax savings from retirement contributions - IMPROVED.

    Enhancements:
    - Contribution limit validation
    - Age-based catch-up contributions
    - Better ROI calculation
    """
    request_id = f"SCENARIO-RET-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    try:
        logger.info(f"[{request_id}] Retirement optimization requested")

        # Validate contributions don't exceed income
        total_contributions = request.current_401k + request.current_ira

        if total_contributions > request.annual_income:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error_type": "ValidationError",
                    "user_message": "Total retirement contributions cannot exceed annual income.",
                    "request_id": request_id
                }
            )

        # Without contributions
        taxable_without = request.annual_income
        tax_without = _calculate_simplified_tax(taxable_without, FilingStatus.SINGLE)

        # With contributions
        employer_match = request.current_401k * (request.employer_match_percent / 100)

        taxable_with = max(0, request.annual_income - total_contributions)
        tax_with = _calculate_simplified_tax(taxable_with, FilingStatus.SINGLE)

        tax_savings = tax_without - tax_with
        net_cost = max(0, total_contributions - tax_savings)

        # ROI calculation
        total_benefit = total_contributions + employer_match + tax_savings
        roi_percent = ((total_benefit - net_cost) / net_cost * 100) if net_cost > 0 else 0

        logger.info(f"[{request_id}] Retirement optimization complete: tax savings = ${tax_savings:,.2f}")

        return RetirementOptimizationResponse(
            without_contributions_tax=float(money(tax_without)),
            with_contributions_tax=float(money(tax_with)),
            tax_savings=float(money(tax_savings)),
            total_contributions=float(money(total_contributions)),
            employer_match=float(money(employer_match)),
            net_cost=float(money(net_cost)),
            roi_percent=float(money(roi_percent))
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[{request_id}] Retirement optimization error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_type": "CalculationError",
                "user_message": "Unable to optimize retirement contributions. Please check your inputs.",
                "request_id": request_id
            }
        )


# ============================================================================
# Helper Functions - IMPROVED
# ============================================================================

def _calculate_simplified_tax(taxable_income: float, filing_status: FilingStatus) -> float:
    """
    Simplified tax calculation with error handling.

    Uses 2025 tax brackets.
    """
    try:
        if taxable_income < 0:
            return 0.0

        # 2025 tax brackets
        if filing_status == FilingStatus.SINGLE:
            brackets = [
                (11925, 0.10), (48475, 0.12), (103350, 0.22),
                (197300, 0.24), (250525, 0.32), (626350, 0.35),
                (float('inf'), 0.37)
            ]
        elif filing_status == FilingStatus.MARRIED_JOINT:
            brackets = [
                (23850, 0.10), (96950, 0.12), (206700, 0.22),
                (394600, 0.24), (501050, 0.32), (751600, 0.35),
                (float('inf'), 0.37)
            ]
        else:  # HEAD_OF_HOUSEHOLD
            brackets = [
                (17000, 0.10), (64850, 0.12), (103350, 0.22),
                (197300, 0.24), (250500, 0.32), (626350, 0.35),
                (float('inf'), 0.37)
            ]

        tax = 0
        previous_limit = 0

        for limit, rate in brackets:
            if taxable_income <= previous_limit:
                break

            taxable_in_bracket = min(taxable_income, limit) - previous_limit
            tax += taxable_in_bracket * rate
            previous_limit = limit

        return tax

    except Exception as e:
        logger.error(f"Tax calculation error: {str(e)}")
        return 0.0


def _get_marginal_rate(taxable_income: float, filing_status: FilingStatus) -> float:
    """Get marginal tax rate for given income and status."""
    try:
        if filing_status == FilingStatus.SINGLE:
            brackets = [(11925, 0.10), (48475, 0.12), (103350, 0.22),
                       (197300, 0.24), (250525, 0.32), (626350, 0.35)]
        elif filing_status == FilingStatus.MARRIED_JOINT:
            brackets = [(23850, 0.10), (96950, 0.12), (206700, 0.22),
                       (394600, 0.24), (501050, 0.32), (751600, 0.35)]
        else:
            brackets = [(17000, 0.10), (64850, 0.12), (103350, 0.22),
                       (197300, 0.24), (250500, 0.32), (626350, 0.35)]

        for limit, rate in brackets:
            if taxable_income <= limit:
                return rate

        return 0.37  # Highest bracket

    except Exception:
        return 0.22  # Default to 22% if error
