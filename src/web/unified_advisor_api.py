"""
Unified Tax Advisor API

The single API that delivers the vision:
- Upload documents → OCR extraction
- Intelligent tax calculation (2025 compliant)
- CPA-level advisory with detailed computations
- Draft forms ready for CPA review

NO ONE IN USA HAS DONE THIS.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import logging
import tempfile
import os
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

# Import unified advisor
try:
    from services.unified_tax_advisor import (
        UnifiedTaxAdvisor,
        TaxProfile,
        AdvisoryReport,
        CPAInsight,
        AdvisoryComplexity,
        quick_advisory
    )
    ADVISOR_AVAILABLE = True
except ImportError as e:
    ADVISOR_AVAILABLE = False
    import_error = str(e)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/advisor", tags=["Unified Tax Advisor"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class QuickAdvisoryInput(BaseModel):
    """Input for quick advisory without document upload."""
    # Filing info
    filing_status: str = Field(default="single", description="single, married_filing_jointly, married_filing_separately, head_of_household, qualifying_widow")
    tax_year: int = Field(default=2025)
    state: str = Field(default="CA")

    # Income
    wages: float = Field(default=0, ge=0)
    interest_income: float = Field(default=0, ge=0)
    dividend_income: float = Field(default=0, ge=0)
    qualified_dividends: float = Field(default=0, ge=0)
    capital_gains_short: float = Field(default=0)
    capital_gains_long: float = Field(default=0)
    business_income: float = Field(default=0)
    rental_income: float = Field(default=0)
    k1_income: float = Field(default=0)
    social_security_benefits: float = Field(default=0, ge=0)
    retirement_distributions: float = Field(default=0, ge=0)
    other_income: float = Field(default=0)

    # Adjustments
    student_loan_interest: float = Field(default=0, ge=0)
    hsa_contributions: float = Field(default=0, ge=0)
    traditional_ira_contributions: float = Field(default=0, ge=0)

    # Deductions
    medical_expenses: float = Field(default=0, ge=0)
    state_local_taxes_paid: float = Field(default=0, ge=0)
    real_estate_taxes: float = Field(default=0, ge=0)
    mortgage_interest: float = Field(default=0, ge=0)
    charitable_cash: float = Field(default=0, ge=0)
    charitable_noncash: float = Field(default=0, ge=0)

    # Credits
    child_tax_credit_eligible: int = Field(default=0, ge=0)
    dependent_care_expenses: float = Field(default=0, ge=0)
    education_expenses: float = Field(default=0, ge=0)
    residential_energy_improvements: float = Field(default=0, ge=0)

    # Payments
    federal_withholding: float = Field(default=0, ge=0)
    estimated_payments: float = Field(default=0, ge=0)

    # Self-employment
    has_self_employment: bool = Field(default=False)
    se_gross_receipts: float = Field(default=0, ge=0)
    se_expenses: float = Field(default=0, ge=0)


class InsightResponse(BaseModel):
    """A single CPA insight."""
    id: str
    category: str
    priority: str
    title: str
    summary: str
    detailed_explanation: str
    estimated_savings: float
    confidence: float
    irs_reference: str
    action_required: str
    requires_professional: bool
    computation_details: Dict[str, Any]


class AdvisoryResponse(BaseModel):
    """Complete advisory report response."""
    id: str
    generated_at: str
    tax_year: int

    # Taxpayer
    taxpayer_name: str
    filing_status: str
    complexity: str

    # Tax position
    gross_income: float
    adjusted_gross_income: float
    taxable_income: float
    federal_tax: float
    self_employment_tax: float
    total_tax: float
    total_payments: float
    refund_or_due: float
    effective_tax_rate: float
    marginal_tax_rate: float

    # Advisory
    total_potential_savings: float
    insights_count: int
    insights: List[InsightResponse]

    # Forms
    forms_required: List[str]

    # Computation
    computation_breakdown: Dict[str, Any]


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/health")
async def advisor_health_check():
    """Check if unified advisor is operational."""
    return {
        "status": "operational" if ADVISOR_AVAILABLE else "unavailable",
        "advisor_available": ADVISOR_AVAILABLE,
        "tax_year": 2025,
        "capabilities": [
            "Document OCR extraction",
            "2025 tax calculation",
            "CPA-level advisory",
            "Multi-strategy optimization",
            "Draft form generation"
        ],
        "timestamp": datetime.now().isoformat()
    }


@router.post("/quick", response_model=AdvisoryResponse)
async def quick_advisory_endpoint(input_data: QuickAdvisoryInput):
    """
    Generate CPA-level advisory from manual inputs.

    No document upload required - just enter your tax data and get
    comprehensive advisory with savings opportunities.
    """
    if not ADVISOR_AVAILABLE:
        raise HTTPException(status_code=501, detail="Unified advisor not available")

    try:
        advisor = UnifiedTaxAdvisor(tax_year=input_data.tax_year)

        # Build profile from input
        profile = TaxProfile(
            filing_status=input_data.filing_status,
            tax_year=input_data.tax_year,
            state=input_data.state,
            wages=input_data.wages,
            interest_income=input_data.interest_income,
            dividend_income=input_data.dividend_income,
            qualified_dividends=input_data.qualified_dividends,
            capital_gains_short=input_data.capital_gains_short,
            capital_gains_long=input_data.capital_gains_long,
            business_income=input_data.business_income,
            rental_income=input_data.rental_income,
            k1_income=input_data.k1_income,
            social_security_benefits=input_data.social_security_benefits,
            retirement_distributions=input_data.retirement_distributions,
            other_income=input_data.other_income,
            student_loan_interest=input_data.student_loan_interest,
            hsa_contributions=input_data.hsa_contributions,
            traditional_ira_contributions=input_data.traditional_ira_contributions,
            medical_expenses=input_data.medical_expenses,
            state_local_taxes_paid=input_data.state_local_taxes_paid,
            real_estate_taxes=input_data.real_estate_taxes,
            mortgage_interest=input_data.mortgage_interest,
            charitable_cash=input_data.charitable_cash,
            charitable_noncash=input_data.charitable_noncash,
            child_tax_credit_eligible=input_data.child_tax_credit_eligible,
            dependent_care_expenses=input_data.dependent_care_expenses,
            education_expenses=input_data.education_expenses,
            residential_energy_improvements=input_data.residential_energy_improvements,
            federal_withholding=input_data.federal_withholding,
            estimated_payments=input_data.estimated_payments,
            has_self_employment=input_data.has_self_employment,
            se_gross_receipts=input_data.se_gross_receipts,
            se_expenses=input_data.se_expenses
        )

        # Calculate and generate advisory
        calculation = advisor.calculate_taxes(profile)
        report = advisor.generate_advisory_report(profile, calculation)

        return _format_advisory_response(report)

    except Exception as e:
        logger.exception(f"Advisory generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate advisory. Please check your input data and try again.")


# File upload validation - use shared utility
from web.helpers.file_validation import validate_uploaded_file, MAX_FILE_SIZE


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None)
):
    """
    Upload a tax document for OCR processing.

    Supports: W-2, 1099-INT, 1099-DIV, 1099-B, 1099-NEC, 1099-MISC,
    K-1, 1098, 1098-T, SSA-1099, and more.
    """
    if not ADVISOR_AVAILABLE:
        raise HTTPException(status_code=501, detail="Unified advisor not available")

    try:
        # Read and validate file first
        content = await file.read()
        validate_uploaded_file(file, content)

        advisor = UnifiedTaxAdvisor()

        # Save validated file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Process document
            from services.unified_tax_advisor import DocumentType
            doc_type = None
            if document_type:
                try:
                    doc_type = DocumentType(document_type)
                except ValueError:
                    pass

            extracted = advisor.process_document(tmp_path, doc_type)

            return {
                "status": "processed",
                "document_id": extracted.id,
                "document_type": extracted.document_type.value,
                "extracted_fields": extracted.extracted_fields,
                "ocr_confidence": extracted.ocr_confidence,
                "extraction_confidence": extracted.extraction_confidence,
                "needs_review": extracted.needs_review,
                "review_notes": extracted.review_notes,
                "payer_ein": extracted.payer_ein
            }

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except Exception as e:
        logger.exception(f"Document processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process document. Please ensure the file is valid and try again.")


@router.post("/full-advisory")
async def full_advisory_with_documents(
    documents: List[UploadFile] = File(None),
    user_inputs: str = Form(None)
):
    """
    Generate complete advisory from uploaded documents and additional inputs.

    This is the full flow:
    1. OCR all uploaded documents
    2. Extract and aggregate tax data
    3. Apply user overrides/additions
    4. Run 2025-compliant tax calculation
    5. Generate CPA-level advisory
    6. Return comprehensive report with draft form list
    """
    if not ADVISOR_AVAILABLE:
        raise HTTPException(status_code=501, detail="Unified advisor not available")

    # Validate document count
    if documents and len(documents) > 25:
        raise HTTPException(status_code=400, detail="Maximum 25 documents allowed per request")

    try:
        import json
        advisor = UnifiedTaxAdvisor()

        # Process documents with validation
        extracted_docs = []
        if documents:
            for doc_file in documents:
                # Read and validate each file
                content = await doc_file.read()
                validate_uploaded_file(doc_file, content)

                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(doc_file.filename)[1]) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name

                try:
                    extracted = advisor.process_document(tmp_path)
                    extracted_docs.append(extracted)
                finally:
                    os.unlink(tmp_path)

        # Parse user inputs
        inputs = {}
        if user_inputs:
            try:
                inputs = json.loads(user_inputs)
            except json.JSONDecodeError:
                pass

        # Build profile
        profile = advisor.build_profile_from_documents(extracted_docs, inputs)

        # Calculate taxes
        calculation = advisor.calculate_taxes(profile)

        # Generate advisory
        report = advisor.generate_advisory_report(profile, calculation)

        # Return comprehensive response
        return {
            "advisory": _format_advisory_response(report),
            "documents_processed": [
                {
                    "id": doc.id,
                    "type": doc.document_type.value,
                    "confidence": doc.extraction_confidence,
                    "fields_extracted": len(doc.extracted_fields)
                }
                for doc in extracted_docs
            ],
            "complexity": profile.complexity.value,
            "forms_required": report.forms_required
        }

    except Exception as e:
        logger.exception(f"Full advisory error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate advisory. Please check your documents and inputs.")


@router.get("/insights/{category}")
async def get_insights_by_category(category: str):
    """
    Get detailed explanation of tax optimization strategies by category.

    Categories: retirement, deductions, credits, investment, entity, timing
    """
    insights_library = {
        "retirement": {
            "title": "Retirement Tax Optimization",
            "strategies": [
                {
                    "name": "401(k) Maximization",
                    "description": "Contribute up to $23,500 (2025) to reduce taxable income",
                    "potential_savings": "Up to $8,695 at 37% bracket",
                    "irs_reference": "IRC §402(g)"
                },
                {
                    "name": "Traditional IRA Deduction",
                    "description": "Deduct up to $7,000 ($8,000 if 50+)",
                    "potential_savings": "Up to $2,960 at 37% bracket",
                    "irs_reference": "IRC §219"
                },
                {
                    "name": "HSA Triple Tax Advantage",
                    "description": "Tax-free contributions, growth, and withdrawals for medical",
                    "potential_savings": "Up to $3,163 plus FICA savings",
                    "irs_reference": "IRC §223"
                },
                {
                    "name": "Backdoor Roth Conversion",
                    "description": "For high earners above Roth IRA income limits",
                    "potential_savings": "Tax-free growth for decades",
                    "irs_reference": "IRC §408A"
                }
            ]
        },
        "deductions": {
            "title": "Deduction Optimization",
            "strategies": [
                {
                    "name": "Bunching Strategy",
                    "description": "Alternate between itemizing and standard deduction",
                    "potential_savings": "Varies based on deductible expenses",
                    "irs_reference": "Publication 17"
                },
                {
                    "name": "Charitable Bunching",
                    "description": "Donate multiple years' contributions in one year",
                    "potential_savings": "Can add $5,000+ in extra deductions",
                    "irs_reference": "IRC §170"
                },
                {
                    "name": "Donor Advised Fund",
                    "description": "Get immediate deduction, distribute to charities over time",
                    "potential_savings": "Immediate large deduction",
                    "irs_reference": "IRC §170(f)(18)"
                },
                {
                    "name": "Qualified Charitable Distribution",
                    "description": "Age 70.5+: donate directly from IRA, bypasses income",
                    "potential_savings": "Up to $105,000 tax-free from IRA",
                    "irs_reference": "IRC §408(d)(8)"
                }
            ]
        },
        "investment": {
            "title": "Investment Tax Optimization",
            "strategies": [
                {
                    "name": "Tax-Loss Harvesting",
                    "description": "Sell losers to offset gains, keep portfolio balanced",
                    "potential_savings": "Offset gains + $3,000 ordinary income",
                    "irs_reference": "IRC §1211"
                },
                {
                    "name": "Long-Term Holding",
                    "description": "Hold investments 1+ year for preferential rates",
                    "potential_savings": "Save up to 17% vs short-term rates",
                    "irs_reference": "IRC §1(h)"
                },
                {
                    "name": "Municipal Bond Income",
                    "description": "Tax-free interest, exempt from federal and possibly state",
                    "potential_savings": "Effective yield boost of 30%+",
                    "irs_reference": "IRC §103"
                },
                {
                    "name": "Opportunity Zone Investment",
                    "description": "Defer and potentially exclude capital gains",
                    "potential_savings": "10-15% exclusion + deferral",
                    "irs_reference": "IRC §1400Z-2"
                }
            ]
        },
        "entity": {
            "title": "Entity Structure Optimization",
            "strategies": [
                {
                    "name": "S-Corporation Election",
                    "description": "Pay reasonable salary, take distributions without SE tax",
                    "potential_savings": "$5,000-$20,000+ for profitable businesses",
                    "irs_reference": "IRC §1361"
                },
                {
                    "name": "QBI Deduction Optimization",
                    "description": "Structure to maximize 20% qualified business income deduction",
                    "potential_savings": "Up to 20% of business income",
                    "irs_reference": "IRC §199A"
                },
                {
                    "name": "Reasonable Compensation Analysis",
                    "description": "Balance salary vs distributions to minimize total tax",
                    "potential_savings": "Optimizes payroll + income tax",
                    "irs_reference": "Rev Rul 59-221"
                }
            ]
        },
        "credits": {
            "title": "Tax Credit Optimization",
            "strategies": [
                {
                    "name": "Child Tax Credit",
                    "description": "$2,000 per qualifying child under 17",
                    "potential_savings": "Up to $2,000/child (partially refundable)",
                    "irs_reference": "IRC §24"
                },
                {
                    "name": "American Opportunity Credit",
                    "description": "Up to $2,500 per student for higher education",
                    "potential_savings": "$2,500/student (40% refundable)",
                    "irs_reference": "IRC §25A"
                },
                {
                    "name": "Residential Clean Energy Credit",
                    "description": "30% of solar, wind, geothermal improvements",
                    "potential_savings": "No cap on credit amount",
                    "irs_reference": "IRC §25D"
                },
                {
                    "name": "Electric Vehicle Credit",
                    "description": "Up to $7,500 for new EVs, $4,000 for used",
                    "potential_savings": "$4,000-$7,500 per vehicle",
                    "irs_reference": "IRC §30D"
                }
            ]
        }
    }

    if category.lower() not in insights_library:
        raise HTTPException(
            status_code=404,
            detail=f"Category not found. Available: {list(insights_library.keys())}"
        )

    return insights_library[category.lower()]


@router.get("/2025-limits")
async def get_2025_tax_limits():
    """
    Get all 2025 tax limits, thresholds, and parameters.

    This is the authoritative source for 2025 tax year values.
    """
    return {
        "tax_year": 2025,
        "source": "IRS Revenue Procedures and Notices",
        "federal_brackets": {
            "single": [
                {"rate": 0.10, "up_to": 11925},
                {"rate": 0.12, "up_to": 48475},
                {"rate": 0.22, "up_to": 103350},
                {"rate": 0.24, "up_to": 197300},
                {"rate": 0.32, "up_to": 250525},
                {"rate": 0.35, "up_to": 626350},
                {"rate": 0.37, "up_to": "unlimited"}
            ],
            "married_filing_jointly": [
                {"rate": 0.10, "up_to": 23850},
                {"rate": 0.12, "up_to": 96950},
                {"rate": 0.22, "up_to": 206700},
                {"rate": 0.24, "up_to": 394600},
                {"rate": 0.32, "up_to": 501050},
                {"rate": 0.35, "up_to": 751600},
                {"rate": 0.37, "up_to": "unlimited"}
            ]
        },
        "standard_deductions": {
            "single": 15750,
            "married_filing_jointly": 31500,
            "married_filing_separately": 15750,
            "head_of_household": 23850,
            "additional_65_or_blind_single": 1950,
            "additional_65_or_blind_married": 1550
        },
        "capital_gains_brackets": {
            "0_percent_up_to": {
                "single": 48350,
                "married_filing_jointly": 96700
            },
            "15_percent_up_to": {
                "single": 533400,
                "married_filing_jointly": 600050
            },
            "20_percent": "above 15% threshold"
        },
        "contribution_limits": {
            "401k": 23500,
            "401k_catch_up_50_plus": 7500,
            "ira": 7000,
            "ira_catch_up_50_plus": 1000,
            "hsa_individual": 4300,
            "hsa_family": 8550,
            "hsa_catch_up_55_plus": 1000
        },
        "social_security": {
            "wage_base": 176100,
            "tax_rate_employee": 0.062,
            "tax_rate_employer": 0.062,
            "tax_rate_self_employed": 0.124
        },
        "medicare": {
            "tax_rate_employee": 0.0145,
            "tax_rate_employer": 0.0145,
            "tax_rate_self_employed": 0.029,
            "additional_medicare_threshold_single": 200000,
            "additional_medicare_threshold_mfj": 250000,
            "additional_medicare_rate": 0.009
        },
        "niit": {
            "rate": 0.038,
            "threshold_single": 200000,
            "threshold_mfj": 250000
        },
        "qbi_deduction": {
            "rate": 0.20,
            "threshold_single": 191950,
            "threshold_mfj": 383900,
            "phase_in_range": 100000
        },
        "credits": {
            "child_tax_credit": 2000,
            "child_tax_credit_refundable_max": 1700,
            "child_age_limit": 17,
            "dependent_care_max_one_child": 3000,
            "dependent_care_max_two_plus": 6000,
            "eitc_max_no_children": 649,
            "eitc_max_one_child": 4328,
            "eitc_max_two_children": 7152,
            "eitc_max_three_plus_children": 8046,
            "aotc_max": 2500,
            "lifetime_learning_credit_max": 2000
        },
        "salt_cap": 10000,
        "gift_tax_exclusion": 19000,
        "estate_tax_exemption": 13990000
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _format_advisory_response(report: AdvisoryReport) -> AdvisoryResponse:
    """Format advisory report for API response."""
    return AdvisoryResponse(
        id=report.id,
        generated_at=report.generated_at.isoformat(),
        tax_year=report.tax_year,
        taxpayer_name=report.taxpayer_name,
        filing_status=report.filing_status,
        complexity=report.complexity.value,
        gross_income=float(money(report.gross_income)),
        adjusted_gross_income=float(money(report.adjusted_gross_income)),
        taxable_income=float(money(report.taxable_income)),
        federal_tax=float(money(report.federal_tax)),
        self_employment_tax=float(money(report.self_employment_tax)),
        total_tax=float(money(report.total_tax)),
        total_payments=float(money(report.total_payments)),
        refund_or_due=float(money(report.refund_or_due)),
        effective_tax_rate=round(report.effective_tax_rate, 4),
        marginal_tax_rate=round(report.marginal_tax_rate, 4),
        total_potential_savings=float(money(report.total_potential_savings)),
        insights_count=len(report.insights),
        insights=[
            InsightResponse(
                id=i.id,
                category=i.category,
                priority=i.priority,
                title=i.title,
                summary=i.summary,
                detailed_explanation=i.detailed_explanation,
                estimated_savings=float(money(i.estimated_savings)),
                confidence=float(money(i.confidence)),
                irs_reference=i.irs_reference,
                action_required=i.action_required,
                requires_professional=i.requires_professional,
                computation_details=i.computation_details
            )
            for i in report.insights
        ],
        forms_required=report.forms_required,
        computation_breakdown=report.computation_breakdown
    )
