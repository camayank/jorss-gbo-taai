"""
Filing Package Export API

Generates comprehensive filing packages for external e-filing.
Exports in multiple formats: JSON, XML, PDF bundle.

NOTE: This platform does NOT e-file directly with IRS.
These packages are designed for CPAs to import into their preferred e-filing software.
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import json
import logging
import io
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from calculator.decimal_math import money, to_decimal

try:
    from rbac.dependencies import require_auth, AuthContext
    from rbac.roles import Role
except ImportError:
    class AuthContext:
        user_id: Optional[str] = None
        role: Any = None
    class Role:
        PARTNER = "partner"
        STAFF = "staff"
    def require_auth():
        return AuthContext()

try:
    from database.session_persistence import get_session_persistence
except ImportError:
    def get_session_persistence():
        raise HTTPException(500, "Session persistence not available")

try:
    from rbac.feature_access_control import require_feature, Features
except ImportError:
    def require_feature(feature):
        return lambda x: x
    class Features:
        FILING_PACKAGE = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/filing-package", tags=["filing-package"])


# =============================================================================
# MODELS
# =============================================================================

class ExportFormat(str, Enum):
    """Supported export formats"""
    JSON = "json"           # Universal JSON format
    XML = "xml"             # XML format for tax software
    PDF_BUNDLE = "pdf"      # ZIP with all PDFs
    LACERTE = "lacerte"     # Lacerte import format
    PROCONNECT = "proconnect"  # ProConnect import format


class FilingPackageRequest(BaseModel):
    """Request to generate a filing package"""
    session_id: str = Field(..., description="Tax return session ID")
    format: ExportFormat = Field(default=ExportFormat.JSON)
    include_supporting_docs: bool = Field(default=True)
    include_computation: bool = Field(default=True)
    preparer_notes: Optional[str] = None


class FilingPackageResponse(BaseModel):
    """Filing package metadata"""
    package_id: str
    session_id: str
    format: str
    created_at: datetime
    download_url: str
    contents: List[str]
    warnings: List[str] = []


# =============================================================================
# FILING PACKAGE GENERATOR
# =============================================================================

class FilingPackageGenerator:
    """Generates filing packages in various formats."""

    # Standard IRS form mapping
    FORM_MAPPING = {
        "1040": {"name": "Form 1040", "description": "U.S. Individual Income Tax Return"},
        "1040_SR": {"name": "Form 1040-SR", "description": "U.S. Tax Return for Seniors"},
        "schedule_a": {"name": "Schedule A", "description": "Itemized Deductions"},
        "schedule_b": {"name": "Schedule B", "description": "Interest and Ordinary Dividends"},
        "schedule_c": {"name": "Schedule C", "description": "Profit or Loss From Business"},
        "schedule_d": {"name": "Schedule D", "description": "Capital Gains and Losses"},
        "schedule_e": {"name": "Schedule E", "description": "Supplemental Income and Loss"},
        "schedule_se": {"name": "Schedule SE", "description": "Self-Employment Tax"},
        "form_8949": {"name": "Form 8949", "description": "Sales and Dispositions of Capital Assets"},
    }

    def __init__(self, session_data: Dict[str, Any]):
        self.session_data = session_data
        self.tax_year = session_data.get("tax_year", 2024)
        self.warnings = []

    def generate_json(self) -> Dict[str, Any]:
        """Generate universal JSON filing package."""
        package = {
            "metadata": {
                "format_version": "1.0",
                "platform": "CA4CPA",
                "generated_at": datetime.utcnow().isoformat(),
                "tax_year": self.tax_year,
                "package_type": "filing_package",
                "note": "This package is for import into external e-filing software. "
                        "CA4CPA does not file directly with the IRS.",
            },
            "taxpayer": self._extract_taxpayer_info(),
            "filing_status": self._extract_filing_status(),
            "income": self._extract_income(),
            "deductions": self._extract_deductions(),
            "credits": self._extract_credits(),
            "taxes": self._extract_taxes(),
            "payments": self._extract_payments(),
            "refund_or_owed": self._calculate_refund_owed(),
            "forms": self._get_required_forms(),
            "schedules": self._get_required_schedules(),
            "supporting_data": self._extract_supporting_data(),
        }

        return package

    def generate_xml(self) -> str:
        """Generate XML filing package (compatible with common tax software)."""
        json_data = self.generate_json()

        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append(f'<TaxReturn xmlns="urn:ca4cpa:filing-package:v1" taxYear="{self.tax_year}">')

        xml_lines.append('  <Metadata>')
        xml_lines.append(f'    <GeneratedAt>{datetime.utcnow().isoformat()}</GeneratedAt>')
        xml_lines.append(f'    <Platform>CA4CPA</Platform>')
        xml_lines.append(f'    <FormatVersion>1.0</FormatVersion>')
        xml_lines.append('  </Metadata>')

        # Taxpayer
        taxpayer = json_data.get("taxpayer", {})
        xml_lines.append('  <Taxpayer>')
        xml_lines.append(f'    <FirstName>{self._xml_escape(taxpayer.get("first_name", ""))}</FirstName>')
        xml_lines.append(f'    <LastName>{self._xml_escape(taxpayer.get("last_name", ""))}</LastName>')
        xml_lines.append(f'    <SSN>{taxpayer.get("ssn_masked", "XXX-XX-XXXX")}</SSN>')
        xml_lines.append(f'    <DateOfBirth>{taxpayer.get("date_of_birth", "")}</DateOfBirth>')
        xml_lines.append('  </Taxpayer>')

        # Filing Status
        xml_lines.append(f'  <FilingStatus>{json_data.get("filing_status", {}).get("code", "")}</FilingStatus>')

        # Income
        income = json_data.get("income", {})
        xml_lines.append('  <Income>')
        xml_lines.append(f'    <Wages>{income.get("wages", 0)}</Wages>')
        xml_lines.append(f'    <Interest>{income.get("interest", 0)}</Interest>')
        xml_lines.append(f'    <Dividends>{income.get("dividends", 0)}</Dividends>')
        xml_lines.append(f'    <CapitalGains>{income.get("capital_gains", 0)}</CapitalGains>')
        xml_lines.append(f'    <BusinessIncome>{income.get("business_income", 0)}</BusinessIncome>')
        xml_lines.append(f'    <OtherIncome>{income.get("other_income", 0)}</OtherIncome>')
        xml_lines.append(f'    <TotalIncome>{income.get("total", 0)}</TotalIncome>')
        xml_lines.append('  </Income>')

        # Deductions
        deductions = json_data.get("deductions", {})
        xml_lines.append('  <Deductions>')
        xml_lines.append(f'    <Method>{deductions.get("method", "standard")}</Method>')
        xml_lines.append(f'    <StandardDeduction>{deductions.get("standard_amount", 0)}</StandardDeduction>')
        xml_lines.append(f'    <ItemizedTotal>{deductions.get("itemized_total", 0)}</ItemizedTotal>')
        xml_lines.append(f'    <TotalDeduction>{deductions.get("total", 0)}</TotalDeduction>')
        xml_lines.append('  </Deductions>')

        # Credits
        credits = json_data.get("credits", {})
        xml_lines.append('  <Credits>')
        for credit_name, credit_amount in credits.items():
            if credit_name != "total":
                xml_lines.append(f'    <Credit name="{credit_name}">{credit_amount}</Credit>')
        xml_lines.append(f'    <TotalCredits>{credits.get("total", 0)}</TotalCredits>')
        xml_lines.append('  </Credits>')

        # Taxes
        taxes = json_data.get("taxes", {})
        xml_lines.append('  <Taxes>')
        xml_lines.append(f'    <TaxableIncome>{taxes.get("taxable_income", 0)}</TaxableIncome>')
        xml_lines.append(f'    <TaxLiability>{taxes.get("tax_liability", 0)}</TaxLiability>')
        xml_lines.append(f'    <SelfEmploymentTax>{taxes.get("se_tax", 0)}</SelfEmploymentTax>')
        xml_lines.append(f'    <TotalTax>{taxes.get("total_tax", 0)}</TotalTax>')
        xml_lines.append('  </Taxes>')

        # Payments
        payments = json_data.get("payments", {})
        xml_lines.append('  <Payments>')
        xml_lines.append(f'    <FederalWithholding>{payments.get("federal_withheld", 0)}</FederalWithholding>')
        xml_lines.append(f'    <EstimatedPayments>{payments.get("estimated_payments", 0)}</EstimatedPayments>')
        xml_lines.append(f'    <TotalPayments>{payments.get("total", 0)}</TotalPayments>')
        xml_lines.append('  </Payments>')

        # Result
        result = json_data.get("refund_or_owed", {})
        xml_lines.append('  <Result>')
        xml_lines.append(f'    <Type>{"Refund" if result.get("is_refund") else "AmountOwed"}</Type>')
        xml_lines.append(f'    <Amount>{abs(result.get("amount", 0))}</Amount>')
        xml_lines.append('  </Result>')

        # Forms List
        xml_lines.append('  <RequiredForms>')
        for form in json_data.get("forms", []):
            xml_lines.append(f'    <Form code="{form["code"]}">{self._xml_escape(form["name"])}</Form>')
        xml_lines.append('  </RequiredForms>')

        xml_lines.append('</TaxReturn>')

        return '\n'.join(xml_lines)

    def generate_lacerte_format(self) -> Dict[str, Any]:
        """Generate Lacerte-compatible import format."""
        json_data = self.generate_json()

        # Lacerte uses specific field codes
        lacerte_data = {
            "software": "Lacerte",
            "version": "2024",
            "import_type": "client_data",
            "client": {
                "first_name": json_data["taxpayer"].get("first_name", ""),
                "last_name": json_data["taxpayer"].get("last_name", ""),
                "ssn": json_data["taxpayer"].get("ssn_masked", ""),
                "filing_status": self._map_filing_status_lacerte(json_data["filing_status"].get("code")),
            },
            "income_wages": [
                {
                    "employer": "Imported from CA4CPA",
                    "wages": json_data["income"].get("wages", 0),
                    "federal_withheld": json_data["payments"].get("federal_withheld", 0),
                }
            ],
            "income_interest": json_data["income"].get("interest", 0),
            "income_dividends": json_data["income"].get("dividends", 0),
            "deductions": json_data["deductions"],
            "notes": "Imported from CA4CPA filing package. Please verify all data.",
        }

        return lacerte_data

    def _extract_taxpayer_info(self) -> Dict[str, Any]:
        """Extract taxpayer information from session data."""
        form_data = self.session_data.get("form_data", {})
        personal = form_data.get("personal", {})

        return {
            "first_name": personal.get("firstName", ""),
            "last_name": personal.get("lastName", ""),
            "ssn_masked": "XXX-XX-" + personal.get("ssn", "")[-4:] if personal.get("ssn") else "XXX-XX-XXXX",
            "date_of_birth": personal.get("dateOfBirth", ""),
            "address": personal.get("address", {}),
        }

    def _extract_filing_status(self) -> Dict[str, Any]:
        """Extract filing status."""
        form_data = self.session_data.get("form_data", {})
        status_code = form_data.get("filingStatus", "single")

        status_map = {
            "single": {"code": "1", "name": "Single"},
            "mfj": {"code": "2", "name": "Married Filing Jointly"},
            "mfs": {"code": "3", "name": "Married Filing Separately"},
            "hoh": {"code": "4", "name": "Head of Household"},
            "qw": {"code": "5", "name": "Qualifying Surviving Spouse"},
        }

        return status_map.get(status_code, status_map["single"])

    def _extract_income(self) -> Dict[str, Any]:
        """Extract all income sources."""
        form_data = self.session_data.get("form_data", {})
        income = form_data.get("income", {})
        w2 = income.get("w2", {})

        wages = self._parse_currency(w2.get("wages", ""))
        interest = self._parse_currency(income.get("investments", {}).get("interest", ""))
        dividends = self._parse_currency(income.get("investments", {}).get("dividends", ""))
        capital_gains = self._parse_currency(income.get("investments", {}).get("capitalGains", ""))
        business = self._parse_currency(income.get("selfEmployment", {}).get("grossIncome", ""))

        total = wages + interest + dividends + capital_gains + business

        return {
            "wages": wages,
            "interest": interest,
            "dividends": dividends,
            "capital_gains": capital_gains,
            "business_income": business,
            "other_income": 0,
            "total": total,
        }

    def _extract_deductions(self) -> Dict[str, Any]:
        """Extract deduction information."""
        form_data = self.session_data.get("form_data", {})
        method = form_data.get("deductionMethod", "standard")
        deductions = form_data.get("deductions", {})

        # Standard deduction amounts for 2024
        standard_amounts = {
            "single": 14600,
            "mfj": 29200,
            "mfs": 14600,
            "hoh": 21900,
            "qw": 29200,
        }

        filing_status = form_data.get("filingStatus", "single")
        standard_amount = standard_amounts.get(filing_status, 14600)

        itemized_total = 0
        if method == "itemized":
            itemized_total = sum([
                self._parse_currency(deductions.get("mortgageInterest", "")),
                min(self._parse_currency(deductions.get("salt", "")), 10000),  # SALT cap
                self._parse_currency(deductions.get("charitable", "")),
                self._parse_currency(deductions.get("medical", "")),
            ])

        total = itemized_total if method == "itemized" and itemized_total > standard_amount else standard_amount

        return {
            "method": method,
            "standard_amount": standard_amount,
            "itemized_total": itemized_total,
            "mortgage_interest": self._parse_currency(deductions.get("mortgageInterest", "")),
            "salt": min(self._parse_currency(deductions.get("salt", "")), 10000),
            "charitable": self._parse_currency(deductions.get("charitable", "")),
            "medical": self._parse_currency(deductions.get("medical", "")),
            "total": total,
        }

    def _extract_credits(self) -> Dict[str, Any]:
        """Extract tax credits."""
        form_data = self.session_data.get("form_data", {})
        credits_data = form_data.get("credits", {})

        credits = {}
        total = 0

        for credit_id, credit_info in credits_data.items():
            if credit_info.get("claimed"):
                amount = credit_info.get("amount", 0)
                credits[credit_id] = amount
                total += amount

        credits["total"] = total
        return credits

    def _extract_taxes(self) -> Dict[str, Any]:
        """Calculate tax amounts."""
        income = self._extract_income()
        deductions = self._extract_deductions()

        taxable_income = max(0, income["total"] - deductions["total"])

        # Simplified tax calculation (2024 single brackets)
        def calculate_tax(income: float) -> float:
            if income <= 11600:
                return income * 0.10
            elif income <= 47150:
                return 1160 + (income - 11600) * 0.12
            elif income <= 100525:
                return 5426 + (income - 47150) * 0.22
            else:
                return 17168.50 + (income - 100525) * 0.24

        tax_liability = calculate_tax(taxable_income)
        credits = self._extract_credits()

        return {
            "taxable_income": taxable_income,
            "tax_liability": float(money(tax_liability)),
            "credits_applied": credits.get("total", 0),
            "se_tax": 0,  # Would need Schedule SE data
            "total_tax": float(money(max(0, tax_liability - credits.get("total", 0)))),
        }

    def _extract_payments(self) -> Dict[str, Any]:
        """Extract payment information."""
        form_data = self.session_data.get("form_data", {})
        income = form_data.get("income", {})
        w2 = income.get("w2", {})

        federal_withheld = self._parse_currency(w2.get("federalWithheld", ""))

        return {
            "federal_withheld": federal_withheld,
            "estimated_payments": 0,
            "other_payments": 0,
            "total": federal_withheld,
        }

    def _calculate_refund_owed(self) -> Dict[str, Any]:
        """Calculate refund or amount owed."""
        taxes = self._extract_taxes()
        payments = self._extract_payments()

        difference = payments["total"] - taxes["total_tax"]

        return {
            "total_tax": taxes["total_tax"],
            "total_payments": payments["total"],
            "amount": float(money(abs(difference))),
            "is_refund": difference >= 0,
        }

    def _get_required_forms(self) -> List[Dict[str, str]]:
        """Determine required forms based on data."""
        forms = [{"code": "1040", "name": "Form 1040", "description": "U.S. Individual Income Tax Return"}]

        income = self._extract_income()
        deductions = self._extract_deductions()

        if income.get("interest", 0) > 0 or income.get("dividends", 0) > 0:
            forms.append({"code": "schedule_b", "name": "Schedule B", "description": "Interest and Ordinary Dividends"})

        if income.get("business_income", 0) > 0:
            forms.append({"code": "schedule_c", "name": "Schedule C", "description": "Profit or Loss From Business"})
            forms.append({"code": "schedule_se", "name": "Schedule SE", "description": "Self-Employment Tax"})

        if income.get("capital_gains", 0) != 0:
            forms.append({"code": "schedule_d", "name": "Schedule D", "description": "Capital Gains and Losses"})
            forms.append({"code": "form_8949", "name": "Form 8949", "description": "Sales and Dispositions of Capital Assets"})

        if deductions.get("method") == "itemized":
            forms.append({"code": "schedule_a", "name": "Schedule A", "description": "Itemized Deductions"})

        return forms

    def _get_required_schedules(self) -> List[str]:
        """Get list of required schedule codes."""
        return [f["code"] for f in self._get_required_forms() if f["code"].startswith("schedule_")]

    def _extract_supporting_data(self) -> Dict[str, Any]:
        """Extract supporting documentation info."""
        return {
            "w2_count": 1,  # Would count from actual W-2 uploads
            "1099_count": 0,
            "documents_uploaded": [],
            "missing_documents": [],
        }

    def _parse_currency(self, value: str) -> float:
        """Parse currency string to float."""
        if not value:
            return 0.0
        return float(str(value).replace("$", "").replace(",", "").strip() or 0)

    def _xml_escape(self, text: str) -> str:
        """Escape XML special characters."""
        if not text:
            return ""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

    def _map_filing_status_lacerte(self, status_code: str) -> str:
        """Map filing status to Lacerte codes."""
        mapping = {"1": "S", "2": "MJ", "3": "MS", "4": "HH", "5": "QW"}
        return mapping.get(status_code, "S")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.post("/generate")
async def generate_filing_package(
    request: FilingPackageRequest,
    ctx: AuthContext = Depends(require_auth)
) -> Dict[str, Any]:
    """
    Generate a filing package for external e-filing.

    NOTE: This platform does NOT e-file with the IRS.
    The generated package is for import into external e-filing software.

    Supported formats:
    - JSON: Universal format, compatible with most systems
    - XML: Standard XML format for tax software
    - PDF: ZIP bundle with all draft forms
    - Lacerte: Lacerte import format
    - ProConnect: ProConnect import format

    Requires PARTNER or STAFF role.
    """
    # Check role (only CPAs can generate filing packages)
    if hasattr(ctx, 'role') and ctx.role:
        role_name = ctx.role.name if hasattr(ctx.role, 'name') else str(ctx.role)
        if role_name.upper() not in ("PARTNER", "STAFF", "PLATFORM_ADMIN", "SUPER_ADMIN"):
            raise HTTPException(403, "Only CPAs can generate filing packages")

    try:
        persistence = get_session_persistence()
        session = persistence.load_session(request.session_id)

        if not session:
            raise HTTPException(404, "Session not found")

        session_data = session.data or {}
        generator = FilingPackageGenerator(session_data)

        # Generate based on format
        if request.format == ExportFormat.JSON:
            content = generator.generate_json()
            return {
                "success": True,
                "format": "json",
                "package": content,
                "warnings": generator.warnings,
            }

        elif request.format == ExportFormat.XML:
            content = generator.generate_xml()
            return {
                "success": True,
                "format": "xml",
                "content": content,
                "warnings": generator.warnings,
            }

        elif request.format == ExportFormat.LACERTE:
            content = generator.generate_lacerte_format()
            return {
                "success": True,
                "format": "lacerte",
                "package": content,
                "warnings": generator.warnings,
            }

        else:
            raise HTTPException(400, f"Unsupported format: {request.format}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FILING_PACKAGE] Failed to generate package: {e}")
        raise HTTPException(500, f"Failed to generate filing package: {str(e)}")


@router.get("/{session_id}/download/{format}")
async def download_filing_package(
    session_id: str,
    format: ExportFormat,
    ctx: AuthContext = Depends(require_auth)
) -> Response:
    """
    Download a filing package in the specified format.

    Returns the file directly for download.
    """
    # Check role
    if hasattr(ctx, 'role') and ctx.role:
        role_name = ctx.role.name if hasattr(ctx.role, 'name') else str(ctx.role)
        if role_name.upper() not in ("PARTNER", "STAFF", "PLATFORM_ADMIN", "SUPER_ADMIN"):
            raise HTTPException(403, "Only CPAs can download filing packages")

    try:
        persistence = get_session_persistence()
        session = persistence.load_session(session_id)

        if not session:
            raise HTTPException(404, "Session not found")

        session_data = session.data or {}
        generator = FilingPackageGenerator(session_data)
        tax_year = session_data.get("tax_year", 2024)

        if format == ExportFormat.JSON:
            content = json.dumps(generator.generate_json(), indent=2)
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="filing_package_{tax_year}_{session_id[:8]}.json"'
                }
            )

        elif format == ExportFormat.XML:
            content = generator.generate_xml()
            return Response(
                content=content,
                media_type="application/xml",
                headers={
                    "Content-Disposition": f'attachment; filename="filing_package_{tax_year}_{session_id[:8]}.xml"'
                }
            )

        elif format == ExportFormat.LACERTE:
            content = json.dumps(generator.generate_lacerte_format(), indent=2)
            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="lacerte_import_{tax_year}_{session_id[:8]}.json"'
                }
            )

        else:
            raise HTTPException(400, f"Unsupported format for download: {format}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FILING_PACKAGE] Failed to download package: {e}")
        raise HTTPException(500, f"Failed to download filing package: {str(e)}")


@router.get("/formats")
async def get_supported_formats() -> Dict[str, Any]:
    """
    Get list of supported filing package export formats.
    """
    return {
        "formats": [
            {
                "code": "json",
                "name": "Universal JSON",
                "description": "JSON format compatible with most systems",
                "extension": ".json",
            },
            {
                "code": "xml",
                "name": "Standard XML",
                "description": "XML format for tax software import",
                "extension": ".xml",
            },
            {
                "code": "lacerte",
                "name": "Lacerte Import",
                "description": "Format for Intuit Lacerte import",
                "extension": ".json",
            },
            {
                "code": "proconnect",
                "name": "ProConnect Import",
                "description": "Format for Intuit ProConnect import",
                "extension": ".json",
                "status": "coming_soon",
            },
            {
                "code": "pdf",
                "name": "PDF Bundle",
                "description": "ZIP archive with all draft forms as PDF",
                "extension": ".zip",
                "status": "coming_soon",
            },
        ],
        "note": "CA4CPA does not e-file directly with the IRS. "
                "These packages are for import into your preferred e-filing software.",
    }
