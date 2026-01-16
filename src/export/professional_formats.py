"""Professional Tax Software Export Formats.

Exports tax return data to formats compatible with professional
tax software used by CPAs, EAs, and tax preparers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum
from datetime import datetime
import json
import csv
import io

if TYPE_CHECKING:
    from models.tax_return import TaxReturn


class ExportFormat(Enum):
    """Supported export formats."""
    # Professional software formats
    LACERTE = "lacerte"  # Intuit Lacerte
    PROSERIES = "proseries"  # Intuit ProSeries
    PROCONNECT = "proconnect"  # Intuit ProConnect
    DRAKE = "drake"  # Drake Tax Software
    ULTRATAX = "ultratax"  # Thomson Reuters UltraTax
    AXCESS = "axcess"  # CCH Axcess
    PROSYSTEM = "prosystem"  # CCH ProSystem fx
    TAXSLAYER = "taxslayer_pro"  # TaxSlayer Pro
    TAXACT = "taxact_pro"  # TaxAct Professional

    # Standard formats
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    TXF = "txf"  # Tax eXchange Format

    # IRS formats
    IRS_XML = "irs_xml"  # IRS MeF XML
    STATE_XML = "state_xml"  # State e-file XML


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    format: ExportFormat
    filename: str
    content: str  # Actual export content
    content_type: str
    file_size: int
    timestamp: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportMapping:
    """Mapping between internal fields and export format fields."""
    internal_path: str
    export_field: str
    transform: Optional[str] = None  # Transformation to apply
    required: bool = False


class ProfessionalExporter:
    """
    Exports tax return data to professional tax software formats.

    This exporter supports multiple professional tax preparation
    software packages used by CPAs, EAs, and enrolled tax preparers.
    """

    # Field mappings for different software
    FIELD_MAPPINGS = {
        ExportFormat.LACERTE: {
            "taxpayer.first_name": "client.firstname",
            "taxpayer.last_name": "client.lastname",
            "taxpayer.ssn": "client.ssn",
            "taxpayer.filing_status": "return.filingstatus",
            "income.w2_wages": "income.w2.box1",
            "income.federal_withholding": "income.w2.box2",
            "income.interest_income": "income.1099int.box1",
            "income.dividend_income": "income.1099div.box1a",
            "income.capital_gain_income": "income.schedule_d.netgain",
            "income.self_employment_income": "income.schedule_c.grossreceipts",
            "income.self_employment_expenses": "income.schedule_c.expenses",
            "deductions.mortgage_interest": "deductions.schedule_a.mortgageint",
            "deductions.property_taxes": "deductions.schedule_a.realestatetax",
            "deductions.charitable_cash": "deductions.schedule_a.charitycash",
            "deductions.medical_expenses": "deductions.schedule_a.medical",
        },
        ExportFormat.DRAKE: {
            "taxpayer.first_name": "SCR01.FNAME",
            "taxpayer.last_name": "SCR01.LNAME",
            "taxpayer.ssn": "SCR01.SSN",
            "taxpayer.filing_status": "SCR01.FILSTAT",
            "income.w2_wages": "W2.01.WAGES",
            "income.federal_withholding": "W2.01.FEDWH",
            "income.interest_income": "INT.TOTALINT",
            "income.dividend_income": "DIV.TOTALDIV",
            "income.self_employment_income": "SCH_C.GROSSINC",
            "deductions.mortgage_interest": "SCH_A.MORTINT",
            "deductions.property_taxes": "SCH_A.PROPTAX",
            "deductions.charitable_cash": "SCH_A.CHARCASH",
        },
        ExportFormat.PROSERIES: {
            "taxpayer.first_name": "TaxpayerInfo.FirstName",
            "taxpayer.last_name": "TaxpayerInfo.LastName",
            "taxpayer.ssn": "TaxpayerInfo.SSN",
            "taxpayer.filing_status": "TaxpayerInfo.FilingStatus",
            "income.w2_wages": "Forms.W2[0].Wages",
            "income.federal_withholding": "Forms.W2[0].FedWithheld",
            "income.interest_income": "Forms.Form1099INT.Interest",
            "income.dividend_income": "Forms.Form1099DIV.Dividends",
            "deductions.mortgage_interest": "Schedules.A.MortgageInterest",
            "deductions.property_taxes": "Schedules.A.PropertyTaxes",
        },
    }

    # Filing status mappings per format
    FILING_STATUS_CODES = {
        ExportFormat.LACERTE: {
            "single": "1",
            "married_joint": "2",
            "married_separate": "3",
            "head_of_household": "4",
            "qualifying_widow": "5",
        },
        ExportFormat.DRAKE: {
            "single": "S",
            "married_joint": "MJ",
            "married_separate": "MS",
            "head_of_household": "HH",
            "qualifying_widow": "QW",
        },
    }

    def __init__(self):
        """Initialize the exporter."""
        self._export_history: List[ExportResult] = []

    def export(
        self,
        tax_return: "TaxReturn",
        format: ExportFormat,
        options: Optional[Dict[str, Any]] = None
    ) -> ExportResult:
        """
        Export tax return to specified format.

        Args:
            tax_return: The tax return to export
            format: Target export format
            options: Optional export options

        Returns:
            ExportResult with content and metadata
        """
        options = options or {}

        try:
            if format == ExportFormat.JSON:
                return self._export_json(tax_return, options)
            elif format == ExportFormat.CSV:
                return self._export_csv(tax_return, options)
            elif format == ExportFormat.TXF:
                return self._export_txf(tax_return, options)
            elif format == ExportFormat.XML:
                return self._export_xml(tax_return, options)
            elif format in (ExportFormat.LACERTE, ExportFormat.PROSERIES,
                           ExportFormat.PROCONNECT):
                return self._export_intuit_format(tax_return, format, options)
            elif format == ExportFormat.DRAKE:
                return self._export_drake(tax_return, options)
            elif format in (ExportFormat.ULTRATAX, ExportFormat.AXCESS,
                           ExportFormat.PROSYSTEM):
                return self._export_cch_format(tax_return, format, options)
            else:
                return self._export_generic(tax_return, format, options)
        except Exception as e:
            return ExportResult(
                success=False,
                format=format,
                filename="",
                content="",
                content_type="",
                file_size=0,
                timestamp=datetime.now().isoformat(),
                errors=[str(e)],
            )

    def export_batch(
        self,
        tax_returns: List["TaxReturn"],
        format: ExportFormat,
        options: Optional[Dict[str, Any]] = None
    ) -> List[ExportResult]:
        """Export multiple tax returns."""
        results = []
        for tax_return in tax_returns:
            result = self.export(tax_return, format, options)
            results.append(result)
        return results

    def get_supported_formats(self) -> List[Dict[str, Any]]:
        """Get list of supported export formats with details."""
        return [
            {
                "format": ExportFormat.LACERTE.value,
                "name": "Intuit Lacerte",
                "description": "Professional tax software for high-volume preparers",
                "file_extension": ".lac",
                "category": "professional",
            },
            {
                "format": ExportFormat.PROSERIES.value,
                "name": "Intuit ProSeries",
                "description": "Desktop professional tax software",
                "file_extension": ".prs",
                "category": "professional",
            },
            {
                "format": ExportFormat.PROCONNECT.value,
                "name": "Intuit ProConnect",
                "description": "Cloud-based professional tax software",
                "file_extension": ".json",
                "category": "professional",
            },
            {
                "format": ExportFormat.DRAKE.value,
                "name": "Drake Tax Software",
                "description": "Popular professional tax software",
                "file_extension": ".dra",
                "category": "professional",
            },
            {
                "format": ExportFormat.ULTRATAX.value,
                "name": "Thomson Reuters UltraTax",
                "description": "Enterprise tax preparation software",
                "file_extension": ".utx",
                "category": "professional",
            },
            {
                "format": ExportFormat.JSON.value,
                "name": "JSON",
                "description": "Standard JSON format for data exchange",
                "file_extension": ".json",
                "category": "standard",
            },
            {
                "format": ExportFormat.CSV.value,
                "name": "CSV",
                "description": "Spreadsheet-compatible format",
                "file_extension": ".csv",
                "category": "standard",
            },
            {
                "format": ExportFormat.TXF.value,
                "name": "Tax eXchange Format",
                "description": "Industry standard tax data format",
                "file_extension": ".txf",
                "category": "standard",
            },
            {
                "format": ExportFormat.XML.value,
                "name": "XML",
                "description": "Standard XML format",
                "file_extension": ".xml",
                "category": "standard",
            },
        ]

    def _export_json(
        self, tax_return: "TaxReturn", options: Dict[str, Any]
    ) -> ExportResult:
        """Export to JSON format."""
        data = self._extract_return_data(tax_return)
        content = json.dumps(data, indent=2, default=str)

        filename = self._generate_filename(tax_return, "json")

        return ExportResult(
            success=True,
            format=ExportFormat.JSON,
            filename=filename,
            content=content,
            content_type="application/json",
            file_size=len(content),
            timestamp=datetime.now().isoformat(),
            metadata={"version": "1.0", "tax_year": 2025},
        )

    def _export_csv(
        self, tax_return: "TaxReturn", options: Dict[str, Any]
    ) -> ExportResult:
        """Export to CSV format."""
        data = self._extract_return_data(tax_return)

        # Flatten nested structure for CSV
        flat_data = self._flatten_dict(data)

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header and data
        writer.writerow(["Field", "Value"])
        for key, value in flat_data.items():
            writer.writerow([key, value])

        content = output.getvalue()
        filename = self._generate_filename(tax_return, "csv")

        return ExportResult(
            success=True,
            format=ExportFormat.CSV,
            filename=filename,
            content=content,
            content_type="text/csv",
            file_size=len(content),
            timestamp=datetime.now().isoformat(),
        )

    def _export_txf(
        self, tax_return: "TaxReturn", options: Dict[str, Any]
    ) -> ExportResult:
        """Export to Tax eXchange Format (TXF)."""
        lines = []

        # TXF header
        lines.append("V042")  # TXF version
        lines.append("AGorss-Gbo Tax Software")  # Software ID
        lines.append("D" + datetime.now().strftime("%m/%d/%Y"))  # Date
        lines.append("^")  # Separator

        # Taxpayer info
        taxpayer = tax_return.taxpayer
        lines.append("TD")  # Taxpayer data
        lines.append("N1")  # Primary taxpayer
        lines.append(f"P{taxpayer.first_name} {taxpayer.last_name}")
        lines.append(f"S{self._mask_ssn(taxpayer.ssn)}")
        lines.append("^")

        # Income section
        income = tax_return.income

        # W-2 wages
        w2_wages = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        if w2_wages > 0:
            lines.append("TD")
            lines.append("N462")  # TXF code for wages
            lines.append(f"${w2_wages:.2f}")
            lines.append("^")

        # Interest income
        interest = getattr(income, 'interest_income', 0) or 0
        if interest > 0:
            lines.append("TD")
            lines.append("N480")  # Interest income
            lines.append(f"${interest:.2f}")
            lines.append("^")

        # Dividend income
        dividends = getattr(income, 'dividend_income', 0) or 0
        if dividends > 0:
            lines.append("TD")
            lines.append("N481")  # Dividend income
            lines.append(f"${dividends:.2f}")
            lines.append("^")

        # Capital gains
        cap_gains = getattr(income, 'capital_gain_income', 0) or 0
        if cap_gains != 0:
            lines.append("TD")
            lines.append("N651" if cap_gains > 0 else "N652")  # ST/LT gains
            lines.append(f"${abs(cap_gains):.2f}")
            lines.append("^")

        # Self-employment
        se_income = getattr(income, 'self_employment_income', 0) or 0
        if se_income > 0:
            lines.append("TD")
            lines.append("N502")  # Schedule C income
            lines.append(f"${se_income:.2f}")
            lines.append("^")

        # Deductions
        deductions = tax_return.deductions

        # Mortgage interest
        mortgage = getattr(deductions, 'mortgage_interest', 0) or 0
        if mortgage > 0:
            lines.append("TD")
            lines.append("N690")  # Home mortgage interest
            lines.append(f"${mortgage:.2f}")
            lines.append("^")

        # Property taxes
        property_tax = getattr(deductions, 'property_taxes', 0) or 0
        if property_tax > 0:
            lines.append("TD")
            lines.append("N683")  # Real estate taxes
            lines.append(f"${property_tax:.2f}")
            lines.append("^")

        # Charitable contributions
        charity = (getattr(deductions, 'charitable_cash', 0) or 0) + \
                  (getattr(deductions, 'charitable_noncash', 0) or 0)
        if charity > 0:
            lines.append("TD")
            lines.append("N681")  # Charitable contributions
            lines.append(f"${charity:.2f}")
            lines.append("^")

        content = "\n".join(lines)
        filename = self._generate_filename(tax_return, "txf")

        return ExportResult(
            success=True,
            format=ExportFormat.TXF,
            filename=filename,
            content=content,
            content_type="text/plain",
            file_size=len(content),
            timestamp=datetime.now().isoformat(),
            metadata={"txf_version": "042"},
        )

    def _export_xml(
        self, tax_return: "TaxReturn", options: Dict[str, Any]
    ) -> ExportResult:
        """Export to generic XML format."""
        data = self._extract_return_data(tax_return)

        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append('<TaxReturn xmlns="http://gorss-gbo.com/tax/2025">')
        xml_lines.append(f'  <TaxYear>2025</TaxYear>')
        xml_lines.append(f'  <GeneratedAt>{datetime.now().isoformat()}</GeneratedAt>')

        # Add sections
        xml_lines.extend(self._dict_to_xml(data, indent=2))

        xml_lines.append('</TaxReturn>')

        content = "\n".join(xml_lines)
        filename = self._generate_filename(tax_return, "xml")

        return ExportResult(
            success=True,
            format=ExportFormat.XML,
            filename=filename,
            content=content,
            content_type="application/xml",
            file_size=len(content),
            timestamp=datetime.now().isoformat(),
        )

    def _export_intuit_format(
        self,
        tax_return: "TaxReturn",
        format: ExportFormat,
        options: Dict[str, Any]
    ) -> ExportResult:
        """Export to Intuit professional format (Lacerte, ProSeries, ProConnect)."""
        mappings = self.FIELD_MAPPINGS.get(format, {})
        filing_codes = self.FILING_STATUS_CODES.get(format, {})

        data = {}
        source_data = self._extract_return_data(tax_return)
        flat_source = self._flatten_dict(source_data)

        # Map fields
        for internal_path, export_field in mappings.items():
            value = flat_source.get(internal_path)
            if value is not None:
                # Apply filing status code mapping
                if "filing_status" in internal_path and value in filing_codes:
                    value = filing_codes[value]
                self._set_nested_value(data, export_field, value)

        # Add metadata
        data["_meta"] = {
            "format": format.value,
            "version": "2025.1",
            "generated": datetime.now().isoformat(),
            "source": "Gorss-Gbo Tax Software",
        }

        content = json.dumps(data, indent=2, default=str)
        extension = {
            ExportFormat.LACERTE: "lac",
            ExportFormat.PROSERIES: "prs",
            ExportFormat.PROCONNECT: "pct",
        }.get(format, "json")

        filename = self._generate_filename(tax_return, extension)

        return ExportResult(
            success=True,
            format=format,
            filename=filename,
            content=content,
            content_type="application/json",
            file_size=len(content),
            timestamp=datetime.now().isoformat(),
            warnings=["Some fields may require manual review in target software"],
            metadata={"target_software": format.value, "mapping_version": "1.0"},
        )

    def _export_drake(
        self, tax_return: "TaxReturn", options: Dict[str, Any]
    ) -> ExportResult:
        """Export to Drake Tax Software format."""
        lines = []

        # Drake uses a proprietary text format
        # This is a simplified representation

        # Header
        lines.append("[RETURN]")
        lines.append(f"TaxYear=2025")
        lines.append(f"Created={datetime.now().strftime('%m/%d/%Y %H:%M:%S')}")
        lines.append("")

        # Taxpayer section
        taxpayer = tax_return.taxpayer
        lines.append("[TAXPAYER]")
        lines.append(f"FirstName={taxpayer.first_name or ''}")
        lines.append(f"LastName={taxpayer.last_name or ''}")
        lines.append(f"SSN={self._mask_ssn(taxpayer.ssn)}")

        # Map filing status
        filing_codes = self.FILING_STATUS_CODES[ExportFormat.DRAKE]
        status = taxpayer.filing_status.value if hasattr(taxpayer.filing_status, 'value') else str(taxpayer.filing_status)
        lines.append(f"FilingStatus={filing_codes.get(status, 'S')}")
        lines.append("")

        # Income section
        income = tax_return.income
        lines.append("[INCOME]")

        # W-2
        w2_wages = income.get_total_wages() if hasattr(income, 'get_total_wages') else 0
        lines.append(f"W2_Wages={w2_wages:.2f}")
        lines.append(f"W2_FedWithheld={getattr(income, 'federal_withholding', 0) or 0:.2f}")

        # Interest/Dividends
        lines.append(f"InterestIncome={getattr(income, 'interest_income', 0) or 0:.2f}")
        lines.append(f"DividendIncome={getattr(income, 'dividend_income', 0) or 0:.2f}")

        # Self-employment
        se_income = getattr(income, 'self_employment_income', 0) or 0
        se_expenses = getattr(income, 'self_employment_expenses', 0) or 0
        lines.append(f"SchC_GrossIncome={se_income:.2f}")
        lines.append(f"SchC_Expenses={se_expenses:.2f}")
        lines.append(f"SchC_NetIncome={max(0, se_income - se_expenses):.2f}")
        lines.append("")

        # Deductions section
        deductions = tax_return.deductions
        lines.append("[DEDUCTIONS]")
        lines.append(f"MortgageInterest={getattr(deductions, 'mortgage_interest', 0) or 0:.2f}")
        lines.append(f"PropertyTax={getattr(deductions, 'property_taxes', 0) or 0:.2f}")
        lines.append(f"CharityCash={getattr(deductions, 'charitable_cash', 0) or 0:.2f}")
        lines.append(f"CharityNonCash={getattr(deductions, 'charitable_noncash', 0) or 0:.2f}")
        lines.append(f"MedicalExpenses={getattr(deductions, 'medical_expenses', 0) or 0:.2f}")
        lines.append("")

        # Results section
        lines.append("[RESULTS]")
        lines.append(f"AGI={tax_return.adjusted_gross_income or 0:.2f}")
        lines.append(f"TaxableIncome={tax_return.taxable_income or 0:.2f}")
        lines.append(f"FederalTax={tax_return.tax_liability or 0:.2f}")
        lines.append(f"RefundOwed={tax_return.refund_or_owed or 0:.2f}")

        content = "\n".join(lines)
        filename = self._generate_filename(tax_return, "dra")

        return ExportResult(
            success=True,
            format=ExportFormat.DRAKE,
            filename=filename,
            content=content,
            content_type="text/plain",
            file_size=len(content),
            timestamp=datetime.now().isoformat(),
            metadata={"drake_version": "2025"},
        )

    def _export_cch_format(
        self,
        tax_return: "TaxReturn",
        format: ExportFormat,
        options: Dict[str, Any]
    ) -> ExportResult:
        """Export to CCH professional formats (UltraTax, Axcess, ProSystem)."""
        # CCH formats use proprietary XML structures
        data = self._extract_return_data(tax_return)

        # Build CCH-style XML
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append(f'<CCHTaxReturn xmlns="http://www.cch.com/tax/{format.value}/2025">')

        # Client information
        xml_lines.append('  <ClientInfo>')
        xml_lines.append(f'    <ClientID>{self._generate_client_id(tax_return)}</ClientID>')
        xml_lines.append(f'    <TaxYear>2025</TaxYear>')
        xml_lines.append(f'    <FilingStatus>{data["taxpayer"]["filing_status"]}</FilingStatus>')
        xml_lines.append('  </ClientInfo>')

        # Taxpayer
        xml_lines.append('  <Taxpayer>')
        xml_lines.append(f'    <FirstName>{data["taxpayer"]["first_name"] or ""}</FirstName>')
        xml_lines.append(f'    <LastName>{data["taxpayer"]["last_name"] or ""}</LastName>')
        xml_lines.append(f'    <SSN>{self._mask_ssn(data["taxpayer"]["ssn"])}</SSN>')
        xml_lines.append('  </Taxpayer>')

        # Income
        xml_lines.append('  <Income>')
        for key, value in data.get("income", {}).items():
            if value and isinstance(value, (int, float)):
                xml_lines.append(f'    <{self._camel_case(key)}>{value:.2f}</{self._camel_case(key)}>')
        xml_lines.append('  </Income>')

        # Deductions
        xml_lines.append('  <Deductions>')
        for key, value in data.get("deductions", {}).items():
            if value and isinstance(value, (int, float)):
                xml_lines.append(f'    <{self._camel_case(key)}>{value:.2f}</{self._camel_case(key)}>')
        xml_lines.append('  </Deductions>')

        # Results
        xml_lines.append('  <Results>')
        xml_lines.append(f'    <AdjustedGrossIncome>{tax_return.adjusted_gross_income or 0:.2f}</AdjustedGrossIncome>')
        xml_lines.append(f'    <TaxableIncome>{tax_return.taxable_income or 0:.2f}</TaxableIncome>')
        xml_lines.append(f'    <TotalTax>{tax_return.tax_liability or 0:.2f}</TotalTax>')
        xml_lines.append(f'    <RefundOrOwed>{tax_return.refund_or_owed or 0:.2f}</RefundOrOwed>')
        xml_lines.append('  </Results>')

        xml_lines.append('</CCHTaxReturn>')

        content = "\n".join(xml_lines)
        extension = {
            ExportFormat.ULTRATAX: "utx",
            ExportFormat.AXCESS: "axx",
            ExportFormat.PROSYSTEM: "psx",
        }.get(format, "xml")

        filename = self._generate_filename(tax_return, extension)

        return ExportResult(
            success=True,
            format=format,
            filename=filename,
            content=content,
            content_type="application/xml",
            file_size=len(content),
            timestamp=datetime.now().isoformat(),
            metadata={"cch_format": format.value},
        )

    def _export_generic(
        self,
        tax_return: "TaxReturn",
        format: ExportFormat,
        options: Dict[str, Any]
    ) -> ExportResult:
        """Generic export fallback."""
        return self._export_json(tax_return, options)

    def _extract_return_data(self, tax_return: "TaxReturn") -> Dict[str, Any]:
        """Extract all data from tax return into dictionary."""
        taxpayer = tax_return.taxpayer
        income = tax_return.income
        deductions = tax_return.deductions
        credits = tax_return.credits

        data = {
            "taxpayer": {
                "first_name": getattr(taxpayer, 'first_name', None),
                "last_name": getattr(taxpayer, 'last_name', None),
                "ssn": getattr(taxpayer, 'ssn', None),
                "filing_status": taxpayer.filing_status.value if hasattr(taxpayer.filing_status, 'value') else str(taxpayer.filing_status),
                "email": getattr(taxpayer, 'email', None),
                "phone": getattr(taxpayer, 'phone', None),
            },
            "income": {
                "w2_wages": income.get_total_wages() if hasattr(income, 'get_total_wages') else 0,
                "federal_withholding": getattr(income, 'federal_withholding', 0),
                "state_withholding": getattr(income, 'state_withholding', 0),
                "interest_income": getattr(income, 'interest_income', 0),
                "dividend_income": getattr(income, 'dividend_income', 0),
                "qualified_dividends": getattr(income, 'qualified_dividends', 0),
                "capital_gain_income": getattr(income, 'capital_gain_income', 0),
                "self_employment_income": getattr(income, 'self_employment_income', 0),
                "self_employment_expenses": getattr(income, 'self_employment_expenses', 0),
                "retirement_income": getattr(income, 'retirement_income', 0),
                "social_security_income": getattr(income, 'social_security_income', 0),
            },
            "deductions": {
                "mortgage_interest": getattr(deductions, 'mortgage_interest', 0),
                "property_taxes": getattr(deductions, 'property_taxes', 0),
                "state_local_taxes": getattr(deductions, 'state_local_taxes', 0),
                "charitable_cash": getattr(deductions, 'charitable_cash', 0),
                "charitable_noncash": getattr(deductions, 'charitable_noncash', 0),
                "medical_expenses": getattr(deductions, 'medical_expenses', 0),
            },
            "results": {
                "adjusted_gross_income": tax_return.adjusted_gross_income,
                "taxable_income": tax_return.taxable_income,
                "deduction_type": getattr(tax_return, 'deduction_type', 'standard'),
                "total_deduction": tax_return.total_deduction if hasattr(tax_return, 'total_deduction') else 0,
                "federal_tax_liability": tax_return.tax_liability,
                "state_tax_liability": getattr(tax_return, 'state_tax_liability', 0),
                "total_withholding": getattr(tax_return, 'total_withholding', 0),
                "refund_or_owed": tax_return.refund_or_owed,
            },
        }

        return data

    def _flatten_dict(
        self, d: Dict[str, Any], parent_key: str = "", sep: str = "."
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _set_nested_value(
        self, d: Dict[str, Any], path: str, value: Any, sep: str = "."
    ) -> None:
        """Set value at nested path in dictionary."""
        keys = path.split(sep)
        current = d
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def _dict_to_xml(
        self, d: Dict[str, Any], indent: int = 0
    ) -> List[str]:
        """Convert dictionary to XML lines."""
        lines = []
        spaces = "  " * indent

        for key, value in d.items():
            tag = self._camel_case(key)
            if isinstance(value, dict):
                lines.append(f"{spaces}<{tag}>")
                lines.extend(self._dict_to_xml(value, indent + 1))
                lines.append(f"{spaces}</{tag}>")
            elif isinstance(value, list):
                for item in value:
                    lines.append(f"{spaces}<{tag}>")
                    if isinstance(item, dict):
                        lines.extend(self._dict_to_xml(item, indent + 1))
                    else:
                        lines.append(f"{spaces}  {item}")
                    lines.append(f"{spaces}</{tag}>")
            elif value is not None:
                if isinstance(value, float):
                    lines.append(f"{spaces}<{tag}>{value:.2f}</{tag}>")
                else:
                    lines.append(f"{spaces}<{tag}>{value}</{tag}>")

        return lines

    def _generate_filename(self, tax_return: "TaxReturn", extension: str) -> str:
        """Generate filename for export."""
        taxpayer = tax_return.taxpayer
        last_name = (getattr(taxpayer, 'last_name', None) or 'taxpayer').replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{last_name}_2025_{timestamp}.{extension}"

    def _generate_client_id(self, tax_return: "TaxReturn") -> str:
        """Generate client ID for professional software."""
        taxpayer = tax_return.taxpayer
        ssn = getattr(taxpayer, 'ssn', '') or ''
        if ssn:
            return f"C{ssn[-4:]}{datetime.now().strftime('%Y')}"
        return f"C{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def _mask_ssn(self, ssn: Optional[str]) -> str:
        """Mask SSN for export (show last 4 only)."""
        if not ssn:
            return "XXX-XX-XXXX"
        cleaned = ssn.replace("-", "")
        if len(cleaned) >= 4:
            return f"XXX-XX-{cleaned[-4:]}"
        return "XXX-XX-XXXX"

    def _camel_case(self, snake_str: str) -> str:
        """Convert snake_case to CamelCase."""
        components = snake_str.split("_")
        return "".join(x.title() for x in components)
