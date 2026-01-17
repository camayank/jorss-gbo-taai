"""Data Import Module.

Import functionality for:
- Prior year tax returns
- Professional tax software exports
- Client data files
- Bulk import for tax preparers
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import json
import csv
# SECURITY: Use safe XML parser to prevent XXE attacks
from security.safe_xml import safe_parse_xml, XMLSecurityError
import xml.etree.ElementTree as ET  # Only for element creation, NOT parsing
from io import StringIO
import re


class ImportFormat(Enum):
    """Supported import formats."""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    TXF = "txf"  # TurboTax Exchange Format
    LACERTE = "lacerte"
    DRAKE = "drake"
    PROSERIES = "proseries"
    ULTRATAX = "ultratax"
    PDF = "pdf"  # Extracted data
    PRIOR_YEAR = "prior_year"


class ImportStatus(Enum):
    """Import operation status."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some data imported
    FAILED = "failed"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ImportField:
    """Represents an imported field."""
    field_name: str
    value: Any
    source_field: Optional[str] = None
    confidence: float = 1.0  # 0-1 confidence score
    needs_review: bool = False
    validation_message: Optional[str] = None


@dataclass
class ImportResult:
    """Result of an import operation."""
    status: ImportStatus
    format_detected: ImportFormat
    fields_imported: List[ImportField] = field(default_factory=list)
    fields_skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    tax_year: Optional[int] = None
    source_file: Optional[str] = None
    import_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate import success rate."""
        total = len(self.fields_imported) + len(self.fields_skipped)
        if total == 0:
            return 0.0
        return len(self.fields_imported) / total

    def get_field(self, field_name: str) -> Optional[ImportField]:
        """Get an imported field by name."""
        for f in self.fields_imported:
            if f.field_name == field_name:
                return f
        return None

    def get_fields_needing_review(self) -> List[ImportField]:
        """Get fields that need manual review."""
        return [f for f in self.fields_imported if f.needs_review]


# Field mappings for different formats
FIELD_MAPPINGS = {
    ImportFormat.JSON: {
        # Standard JSON field names
        "firstName": "first_name",
        "lastName": "last_name",
        "ssn": "ssn",
        "dateOfBirth": "date_of_birth",
        "filingStatus": "filing_status",
        "wages": "w2_wages",
        "federalWithheld": "federal_withholding",
        "stateWithheld": "state_withholding",
        "interestIncome": "interest_income",
        "dividendIncome": "dividend_income",
        "capitalGains": "capital_gains",
        "businessIncome": "business_income",
        "rentalIncome": "rental_income",
        "retirementIncome": "retirement_income",
        "socialSecurity": "social_security_income",
        "mortgageInterest": "mortgage_interest",
        "propertyTaxes": "property_taxes",
        "stateTaxesPaid": "state_taxes_paid",
        "charitableCash": "charitable_cash",
        "charitableNonCash": "charitable_noncash",
    },
    ImportFormat.TXF: {
        # TurboTax Exchange Format codes
        "P": "first_name",
        "S": "ssn",
        "N1": "w2_wages",
        "N2": "federal_withholding",
        "N30": "interest_income",
        "N31": "dividend_income",
        "N77": "mortgage_interest",
        "N78": "property_taxes",
        "N79": "charitable_cash",
    },
    ImportFormat.LACERTE: {
        # Lacerte field IDs
        "1.1": "first_name",
        "1.2": "last_name",
        "1.3": "ssn",
        "2.1": "filing_status",
        "10.1": "w2_wages",
        "10.2": "federal_withholding",
        "11.1": "interest_income",
        "11.2": "dividend_income",
        "12.1": "capital_gains",
        "13.1": "business_income",
        "20.1": "mortgage_interest",
        "20.2": "property_taxes",
        "20.3": "state_taxes_paid",
        "20.4": "charitable_cash",
    },
    ImportFormat.DRAKE: {
        # Drake Software field codes
        "TP_FNAME": "first_name",
        "TP_LNAME": "last_name",
        "TP_SSN": "ssn",
        "TP_DOB": "date_of_birth",
        "FILSTAT": "filing_status",
        "W2_WAGES": "w2_wages",
        "W2_FED_WH": "federal_withholding",
        "W2_ST_WH": "state_withholding",
        "INT_INC": "interest_income",
        "DIV_ORD": "dividend_income",
        "DIV_QUAL": "qualified_dividends",
        "CAP_ST": "short_term_gains",
        "CAP_LT": "long_term_gains",
        "SCH_C_INC": "business_income",
        "SCH_C_EXP": "business_expenses",
        "SCH_E_RENT": "rental_income",
        "MORT_INT": "mortgage_interest",
        "PROP_TAX": "property_taxes",
        "ST_TAX_PD": "state_taxes_paid",
        "CHAR_CASH": "charitable_cash",
        "CHAR_NC": "charitable_noncash",
    },
}


class DataImporter:
    """General-purpose data importer for tax returns."""

    def __init__(self):
        self.supported_formats = list(ImportFormat)
        self.field_mappings = FIELD_MAPPINGS

    def detect_format(self, content: str, filename: Optional[str] = None) -> ImportFormat:
        """Auto-detect the import format."""
        # Check filename extension
        if filename:
            ext = filename.lower().split('.')[-1]
            if ext == 'json':
                return ImportFormat.JSON
            elif ext == 'csv':
                return ImportFormat.CSV
            elif ext == 'xml':
                return ImportFormat.XML
            elif ext == 'txf':
                return ImportFormat.TXF
            elif ext == 'pdf':
                return ImportFormat.PDF

        # Try to detect from content
        content_stripped = content.strip()

        # JSON detection
        if content_stripped.startswith('{') or content_stripped.startswith('['):
            try:
                json.loads(content)
                return ImportFormat.JSON
            except (json.JSONDecodeError, ValueError):
                pass

        # XML detection (using safe parser to prevent XXE)
        if content_stripped.startswith('<?xml') or content_stripped.startswith('<'):
            try:
                safe_parse_xml(content)
                return ImportFormat.XML
            except (ET.ParseError, XMLSecurityError):
                pass

        # TXF detection (starts with V version line)
        if content_stripped.startswith('V'):
            lines = content_stripped.split('\n')
            if len(lines) > 1 and lines[0].startswith('V') and '^' in content:
                return ImportFormat.TXF

        # CSV detection (has commas and consistent column count)
        if ',' in content:
            try:
                reader = csv.reader(StringIO(content))
                rows = list(reader)
                if len(rows) > 1:
                    col_count = len(rows[0])
                    if all(len(row) == col_count for row in rows[:5]):
                        return ImportFormat.CSV
            except (csv.Error, ValueError):
                pass

        # Default to JSON if can't detect
        return ImportFormat.JSON

    def import_data(
        self,
        content: str,
        format_type: Optional[ImportFormat] = None,
        filename: Optional[str] = None,
        tax_year: Optional[int] = None
    ) -> ImportResult:
        """Import tax data from various formats."""
        # Auto-detect format if not specified
        if format_type is None:
            format_type = self.detect_format(content, filename)

        result = ImportResult(
            status=ImportStatus.SUCCESS,
            format_detected=format_type,
            source_file=filename,
            tax_year=tax_year
        )

        try:
            if format_type == ImportFormat.JSON:
                self._import_json(content, result)
            elif format_type == ImportFormat.CSV:
                self._import_csv(content, result)
            elif format_type == ImportFormat.XML:
                self._import_xml(content, result)
            elif format_type == ImportFormat.TXF:
                self._import_txf(content, result)
            elif format_type == ImportFormat.LACERTE:
                self._import_lacerte(content, result)
            elif format_type == ImportFormat.DRAKE:
                self._import_drake(content, result)
            else:
                result.status = ImportStatus.FAILED
                result.errors.append(f"Unsupported format: {format_type}")
        except Exception as e:
            result.status = ImportStatus.FAILED
            result.errors.append(f"Import error: {str(e)}")

        # Validate imported fields
        self._validate_fields(result)

        # Update status based on results
        if result.errors and result.fields_imported:
            result.status = ImportStatus.PARTIAL
        elif result.errors:
            result.status = ImportStatus.FAILED

        return result

    def _import_json(self, content: str, result: ImportResult):
        """Import from JSON format."""
        data = json.loads(content)

        # Handle both single return and list of returns
        if isinstance(data, list):
            data = data[0]  # Take first return
            result.warnings.append("Multiple returns found, importing first only")

        mappings = self.field_mappings.get(ImportFormat.JSON, {})

        for source_field, value in data.items():
            if source_field in mappings:
                target_field = mappings[source_field]
            else:
                # Use source field name if no mapping
                target_field = self._normalize_field_name(source_field)

            if value is not None and value != "":
                result.fields_imported.append(ImportField(
                    field_name=target_field,
                    value=value,
                    source_field=source_field,
                    confidence=1.0
                ))

    def _import_csv(self, content: str, result: ImportResult):
        """Import from CSV format."""
        reader = csv.DictReader(StringIO(content))

        rows = list(reader)
        if not rows:
            result.errors.append("CSV file is empty")
            return

        # Take first row as the return data
        if len(rows) > 1:
            result.warnings.append(f"Multiple rows found ({len(rows)}), importing first only")

        row = rows[0]

        for source_field, value in row.items():
            if value and value.strip():
                target_field = self._normalize_field_name(source_field)
                result.fields_imported.append(ImportField(
                    field_name=target_field,
                    value=self._parse_value(value),
                    source_field=source_field,
                    confidence=0.9  # Slightly lower confidence for CSV
                ))

    def _import_xml(self, content: str, result: ImportResult):
        """Import from XML format (using safe parser to prevent XXE attacks)."""
        root = safe_parse_xml(content)

        # Handle IRS MeF format
        if 'irs' in root.tag.lower() or root.tag == 'Return':
            self._import_mef_xml(root, result)
        else:
            # Generic XML import
            self._import_generic_xml(root, result)

    def _import_mef_xml(self, root: ET.Element, result: ImportResult):
        """Import from IRS MeF XML format."""
        # Navigate the MeF structure
        ns = {'irs': 'http://www.irs.gov/efile'}

        # Try to find common elements
        field_paths = {
            'first_name': ['.//PrimaryFirstName', './/FirstName', './/TaxpayerName/FirstName'],
            'last_name': ['.//PrimaryLastName', './/LastName', './/TaxpayerName/LastName'],
            'ssn': ['.//PrimarySSN', './/SSN', './/TaxpayerSSN'],
            'filing_status': ['.//FilingStatus', './/FilingStatusCd'],
            'w2_wages': ['.//WagesSalariesAndTipsAmt', './/WagesAmt', './/TotalWagesAmt'],
            'federal_withholding': ['.//FederalIncomeTaxWithheldAmt', './/WithholdingAmt'],
            'interest_income': ['.//TaxableInterestAmt', './/InterestIncomeAmt'],
            'dividend_income': ['.//OrdinaryDividendsAmt', './/DividendIncomeAmt'],
            'business_income': ['.//NetProfitOrLossAmt', './/BusinessIncomeAmt'],
            'total_income': ['.//TotalIncomeAmt', './/GrossIncomeAmt'],
            'agi': ['.//AdjustedGrossIncomeAmt', './/AGIAmt'],
            'taxable_income': ['.//TaxableIncomeAmt'],
            'total_tax': ['.//TotalTaxAmt', './/TaxAmt'],
            'refund_amount': ['.//RefundAmt', './/OverpaymentAmt'],
            'amount_owed': ['.//AmountOwedAmt', './/BalanceDueAmt'],
        }

        for field_name, paths in field_paths.items():
            for path in paths:
                elem = root.find(path)
                if elem is not None and elem.text:
                    result.fields_imported.append(ImportField(
                        field_name=field_name,
                        value=self._parse_value(elem.text),
                        source_field=path,
                        confidence=1.0
                    ))
                    break

    def _import_generic_xml(self, root: ET.Element, result: ImportResult):
        """Import from generic XML format."""
        def process_element(elem, prefix=""):
            for child in elem:
                field_name = f"{prefix}{child.tag}" if prefix else child.tag

                if len(child) == 0:  # Leaf node
                    if child.text and child.text.strip():
                        result.fields_imported.append(ImportField(
                            field_name=self._normalize_field_name(field_name),
                            value=self._parse_value(child.text),
                            source_field=field_name,
                            confidence=0.8
                        ))
                else:
                    process_element(child, f"{field_name}_")

        process_element(root)

    def _import_txf(self, content: str, result: ImportResult):
        """Import from TurboTax Exchange Format."""
        lines = content.strip().split('\n')
        mappings = self.field_mappings.get(ImportFormat.TXF, {})

        current_record = {}

        for line in lines:
            if line.startswith('V'):
                # Version line
                continue
            elif line.startswith('A'):
                # Account/software info
                continue
            elif line.startswith('T'):
                # Type definition
                if '^' in line:
                    parts = line.split('^')
                    record_type = parts[0][1:]  # Remove 'T'
                    current_record['type'] = record_type
            elif line.startswith('C'):
                # Copy number
                continue
            elif line.startswith('L'):
                # Line number
                if '^' in line:
                    parts = line.split('^')
                    line_num = parts[0][1:]  # Remove 'L'
                    current_record['line'] = line_num
            elif line.startswith('$'):
                # Dollar amount
                amount = line[1:].replace(',', '')
                if 'type' in current_record:
                    source_field = f"N{current_record['type']}"
                    if source_field in mappings:
                        result.fields_imported.append(ImportField(
                            field_name=mappings[source_field],
                            value=float(amount),
                            source_field=source_field,
                            confidence=1.0
                        ))
            elif line.startswith('P') or line.startswith('S'):
                # Text field (Name, SSN)
                field_type = line[0]
                value = line[1:]
                if field_type in mappings:
                    result.fields_imported.append(ImportField(
                        field_name=mappings[field_type],
                        value=value,
                        source_field=field_type,
                        confidence=1.0
                    ))

    def _import_lacerte(self, content: str, result: ImportResult):
        """Import from Lacerte export format."""
        # Lacerte uses a proprietary format - parse key-value pairs
        mappings = self.field_mappings.get(ImportFormat.LACERTE, {})

        # Parse field=value pairs
        pattern = r'(\d+\.\d+)\s*=\s*(.+?)(?=\n\d+\.\d+|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)

        for field_id, value in matches:
            value = value.strip()
            if field_id in mappings:
                result.fields_imported.append(ImportField(
                    field_name=mappings[field_id],
                    value=self._parse_value(value),
                    source_field=field_id,
                    confidence=1.0
                ))
            else:
                result.fields_skipped.append(field_id)

    def _import_drake(self, content: str, result: ImportResult):
        """Import from Drake Software export format."""
        mappings = self.field_mappings.get(ImportFormat.DRAKE, {})

        # Drake uses pipe-delimited or fixed-width format
        lines = content.strip().split('\n')

        for line in lines:
            # Try pipe-delimited first
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    field_code = parts[0].strip()
                    value = parts[1].strip()

                    if field_code in mappings:
                        result.fields_imported.append(ImportField(
                            field_name=mappings[field_code],
                            value=self._parse_value(value),
                            source_field=field_code,
                            confidence=1.0
                        ))
                    else:
                        result.fields_skipped.append(field_code)
            # Try equals format
            elif '=' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    field_code = parts[0].strip()
                    value = parts[1].strip()

                    if field_code in mappings:
                        result.fields_imported.append(ImportField(
                            field_name=mappings[field_code],
                            value=self._parse_value(value),
                            source_field=field_code,
                            confidence=1.0
                        ))

    def _normalize_field_name(self, name: str) -> str:
        """Normalize field name to snake_case."""
        # Convert camelCase to snake_case
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        normalized = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        # Remove special characters
        normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
        # Remove multiple underscores
        normalized = re.sub(r'_+', '_', normalized)
        return normalized.strip('_')

    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type."""
        if isinstance(value, (int, float)):
            return value

        value = value.strip()

        # Try integer
        if re.match(r'^-?\d+$', value):
            return int(value)

        # Try float (with optional commas)
        cleaned = value.replace(',', '')
        if re.match(r'^-?\d+\.?\d*$', cleaned):
            return float(cleaned)

        # Currency format
        if value.startswith('$'):
            cleaned = value[1:].replace(',', '')
            if re.match(r'^-?\d+\.?\d*$', cleaned):
                return float(cleaned)

        # Boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False

        return value

    def _validate_fields(self, result: ImportResult):
        """Validate imported fields."""
        for field in result.fields_imported:
            # SSN validation
            if field.field_name == 'ssn':
                if not self._validate_ssn(field.value):
                    field.needs_review = True
                    field.validation_message = "SSN format may be invalid"
                    field.confidence = 0.5

            # Date validation
            if 'date' in field.field_name.lower():
                if not self._validate_date(field.value):
                    field.needs_review = True
                    field.validation_message = "Date format needs verification"
                    field.confidence = 0.7

            # Negative income (unusual)
            if 'income' in field.field_name and isinstance(field.value, (int, float)):
                if field.value < 0:
                    field.needs_review = True
                    field.validation_message = "Negative income value - verify this is correct"

            # Very large values
            if isinstance(field.value, (int, float)) and abs(field.value) > 10_000_000:
                field.needs_review = True
                field.validation_message = "Large value - please verify"

    def _validate_ssn(self, ssn: Any) -> bool:
        """Validate SSN format."""
        if not isinstance(ssn, str):
            ssn = str(ssn)
        # Remove dashes and spaces
        ssn = re.sub(r'[-\s]', '', ssn)
        # Should be 9 digits
        return bool(re.match(r'^\d{9}$', ssn))

    def _validate_date(self, date_val: Any) -> bool:
        """Validate date format."""
        if not isinstance(date_val, str):
            return True  # Already parsed

        # Common date patterns
        patterns = [
            r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
            r'^\d{2}/\d{2}/\d{4}$',  # MM/DD/YYYY
            r'^\d{2}-\d{2}-\d{4}$',  # MM-DD-YYYY
        ]
        return any(re.match(p, date_val) for p in patterns)

    def to_tax_return_dict(self, result: ImportResult) -> Dict[str, Any]:
        """Convert import result to a dictionary suitable for TaxReturn."""
        data = {}

        # Group related fields
        personal_info = {}
        income = {}
        deductions = {}
        credits = {}
        withholding = {}

        for field in result.fields_imported:
            name = field.field_name
            value = field.value

            # Personal info
            if name in ['first_name', 'last_name', 'ssn', 'date_of_birth', 'filing_status']:
                personal_info[name] = value
            # Income
            elif 'income' in name or 'wages' in name or 'gains' in name or 'dividend' in name or 'interest' in name:
                income[name] = value
            # Deductions
            elif any(d in name for d in ['mortgage', 'property_tax', 'charitable', 'medical', 'state_tax']):
                deductions[name] = value
            # Withholding
            elif 'withholding' in name or 'withheld' in name:
                withholding[name] = value
            # Everything else
            else:
                data[name] = value

        data['personal_info'] = personal_info
        data['income'] = income
        data['deductions'] = deductions
        data['withholding'] = withholding
        data['import_metadata'] = {
            'source_format': result.format_detected.value,
            'source_file': result.source_file,
            'import_timestamp': result.import_timestamp.isoformat(),
            'success_rate': result.success_rate,
            'fields_needing_review': [f.field_name for f in result.get_fields_needing_review()]
        }

        return data


class PriorYearImporter:
    """Import prior year tax returns for comparison and carryovers."""

    def __init__(self):
        self.data_importer = DataImporter()

    def import_prior_year(
        self,
        content: str,
        prior_year: int,
        format_type: Optional[ImportFormat] = None
    ) -> ImportResult:
        """Import a prior year tax return."""
        result = self.data_importer.import_data(
            content,
            format_type=format_type,
            tax_year=prior_year
        )

        # Add carryover calculations
        if result.status in [ImportStatus.SUCCESS, ImportStatus.PARTIAL]:
            self._calculate_carryovers(result)

        return result

    def _calculate_carryovers(self, result: ImportResult):
        """Calculate carryover amounts from prior year."""
        carryovers = []

        # Capital loss carryover
        cap_loss = result.get_field('capital_loss_carryover')
        net_cap_gain = result.get_field('net_capital_gain')

        if cap_loss or (net_cap_gain and net_cap_gain.value < 0):
            loss_amount = 0
            if cap_loss:
                loss_amount = cap_loss.value
            elif net_cap_gain and net_cap_gain.value < -3000:
                # $3,000 limit applied, remainder carries over
                loss_amount = abs(net_cap_gain.value) - 3000

            if loss_amount > 0:
                carryovers.append(ImportField(
                    field_name='capital_loss_carryover',
                    value=loss_amount,
                    source_field='calculated_from_prior_year',
                    confidence=0.9,
                    needs_review=True,
                    validation_message="Capital loss carryover from prior year"
                ))

        # NOL carryover (business losses)
        nol = result.get_field('net_operating_loss')
        if nol and nol.value < 0:
            carryovers.append(ImportField(
                field_name='nol_carryover',
                value=abs(nol.value),
                source_field='calculated_from_prior_year',
                confidence=0.9,
                needs_review=True,
                validation_message="NOL carryover - verify with IRS rules"
            ))

        # Charitable contribution carryover (over 60% AGI limit)
        charitable = result.get_field('charitable_cash')
        agi = result.get_field('agi')
        if charitable and agi and agi.value > 0:
            limit = agi.value * 0.60
            if charitable.value > limit:
                excess = charitable.value - limit
                carryovers.append(ImportField(
                    field_name='charitable_carryover',
                    value=excess,
                    source_field='calculated_from_prior_year',
                    confidence=0.8,
                    needs_review=True,
                    validation_message="Excess charitable contributions (5-year carryover)"
                ))

        # Add carryovers to result
        result.fields_imported.extend(carryovers)

        if carryovers:
            result.warnings.append(f"Calculated {len(carryovers)} carryover(s) from prior year")

    def get_year_over_year_comparison(
        self,
        current_result: ImportResult,
        prior_result: ImportResult
    ) -> Dict[str, Dict[str, Any]]:
        """Compare current year to prior year data."""
        comparison = {}

        # Fields to compare
        compare_fields = [
            'w2_wages', 'interest_income', 'dividend_income',
            'capital_gains', 'business_income', 'rental_income',
            'total_income', 'agi', 'taxable_income',
            'total_tax', 'refund_amount', 'amount_owed',
            'mortgage_interest', 'property_taxes', 'charitable_cash'
        ]

        for field_name in compare_fields:
            current_field = current_result.get_field(field_name)
            prior_field = prior_result.get_field(field_name)

            if current_field or prior_field:
                current_val = current_field.value if current_field else 0
                prior_val = prior_field.value if prior_field else 0

                change = current_val - prior_val
                pct_change = (change / prior_val * 100) if prior_val != 0 else None

                comparison[field_name] = {
                    'current_year': current_val,
                    'prior_year': prior_val,
                    'change': change,
                    'percent_change': pct_change,
                    'direction': 'increase' if change > 0 else ('decrease' if change < 0 else 'unchanged')
                }

        return comparison


class BulkImporter:
    """Bulk import for tax preparers handling multiple returns."""

    def __init__(self):
        self.data_importer = DataImporter()

    def import_batch(
        self,
        files: List[Tuple[str, str]],  # List of (filename, content)
        format_type: Optional[ImportFormat] = None
    ) -> Dict[str, ImportResult]:
        """Import multiple returns in batch."""
        results = {}

        for filename, content in files:
            result = self.data_importer.import_data(
                content,
                format_type=format_type,
                filename=filename
            )
            results[filename] = result

        return results

    def import_csv_batch(self, content: str) -> List[ImportResult]:
        """Import multiple returns from a single CSV file (one per row)."""
        results = []

        reader = csv.DictReader(StringIO(content))

        for row_num, row in enumerate(reader, start=1):
            result = ImportResult(
                status=ImportStatus.SUCCESS,
                format_detected=ImportFormat.CSV,
                source_file=f"row_{row_num}"
            )

            for field_name, value in row.items():
                if value and value.strip():
                    normalized_name = self.data_importer._normalize_field_name(field_name)
                    result.fields_imported.append(ImportField(
                        field_name=normalized_name,
                        value=self.data_importer._parse_value(value),
                        source_field=field_name,
                        confidence=0.9
                    ))

            self.data_importer._validate_fields(result)
            results.append(result)

        return results

    def generate_batch_report(self, results: Dict[str, ImportResult]) -> Dict[str, Any]:
        """Generate a summary report of batch import."""
        total = len(results)
        successful = sum(1 for r in results.values() if r.status == ImportStatus.SUCCESS)
        partial = sum(1 for r in results.values() if r.status == ImportStatus.PARTIAL)
        failed = sum(1 for r in results.values() if r.status == ImportStatus.FAILED)

        all_errors = []
        all_warnings = []
        fields_needing_review = []

        for filename, result in results.items():
            for error in result.errors:
                all_errors.append(f"{filename}: {error}")
            for warning in result.warnings:
                all_warnings.append(f"{filename}: {warning}")
            for field in result.get_fields_needing_review():
                fields_needing_review.append({
                    'file': filename,
                    'field': field.field_name,
                    'message': field.validation_message
                })

        return {
            'summary': {
                'total_files': total,
                'successful': successful,
                'partial': partial,
                'failed': failed,
                'success_rate': (successful + partial) / total if total > 0 else 0
            },
            'errors': all_errors,
            'warnings': all_warnings,
            'fields_needing_review': fields_needing_review,
            'file_results': {
                filename: {
                    'status': result.status.value,
                    'fields_imported': len(result.fields_imported),
                    'fields_skipped': len(result.fields_skipped),
                    'format': result.format_detected.value
                }
                for filename, result in results.items()
            }
        }

    def validate_batch(self, results: Dict[str, ImportResult]) -> Dict[str, List[str]]:
        """Validate a batch of imported returns for common issues."""
        issues = {}

        for filename, result in results.items():
            file_issues = []

            # Check for missing critical fields
            critical_fields = ['first_name', 'last_name', 'ssn', 'filing_status']
            for field in critical_fields:
                if not result.get_field(field):
                    file_issues.append(f"Missing critical field: {field}")

            # Check for income but no withholding
            wages = result.get_field('w2_wages')
            withholding = result.get_field('federal_withholding')
            if wages and wages.value > 0 and not withholding:
                file_issues.append("W-2 wages present but no federal withholding")

            # Check for invalid filing status
            filing_status = result.get_field('filing_status')
            if filing_status:
                valid_statuses = ['single', 'mfj', 'mfs', 'hoh', 'qw',
                                'married_filing_jointly', 'married_filing_separately',
                                'head_of_household', 'qualifying_widow']
                if str(filing_status.value).lower() not in valid_statuses:
                    file_issues.append(f"Invalid filing status: {filing_status.value}")

            if file_issues:
                issues[filename] = file_issues

        return issues
