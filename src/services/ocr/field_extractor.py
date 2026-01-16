"""
Field Extractor - Extracts structured data from OCR results.

Uses templates and pattern matching to extract specific fields
from tax documents based on document type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Pattern
from decimal import Decimal, InvalidOperation
from datetime import datetime
from enum import Enum

from .ocr_engine import OCRResult, TextBlock, BoundingBox


class FieldType(str, Enum):
    """Types of fields that can be extracted."""
    STRING = "string"
    DECIMAL = "decimal"
    INTEGER = "integer"
    DATE = "date"
    SSN = "ssn"
    EIN = "ein"
    PHONE = "phone"
    ADDRESS = "address"
    BOOLEAN = "boolean"
    CURRENCY = "currency"


@dataclass
class FieldTemplate:
    """Template for extracting a specific field from OCR text."""
    field_name: str
    field_label: str
    field_type: FieldType
    patterns: List[Pattern]
    required: bool = False
    validators: List[Callable[[str], bool]] = field(default_factory=list)
    normalizer: Optional[Callable[[str], Any]] = None
    irs_reference: Optional[str] = None
    target_table: Optional[str] = None
    target_field: Optional[str] = None
    box_number: Optional[str] = None

    def __post_init__(self):
        # Compile patterns if they're strings
        compiled = []
        for p in self.patterns:
            if isinstance(p, str):
                compiled.append(re.compile(p, re.IGNORECASE | re.MULTILINE))
            else:
                compiled.append(p)
        self.patterns = compiled


@dataclass
class ExtractedField:
    """A field extracted from a document."""
    field_name: str
    field_label: str
    raw_value: str
    normalized_value: Any
    field_type: FieldType
    confidence: float
    bbox: Optional[BoundingBox] = None
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    irs_reference: Optional[str] = None
    target_table: Optional[str] = None
    target_field: Optional[str] = None
    box_number: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (JSON serializable)."""
        # Convert Decimal to float for JSON serialization
        normalized = self.normalized_value
        if isinstance(normalized, Decimal):
            normalized = float(normalized)

        return {
            "field_name": self.field_name,
            "field_label": self.field_label,
            "raw_value": self.raw_value,
            "normalized_value": normalized,
            "field_type": self.field_type.value,
            "confidence": self.confidence,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "irs_reference": self.irs_reference,
            "target_table": self.target_table,
            "target_field": self.target_field,
            "box_number": self.box_number,
        }


class FieldExtractor:
    """
    Extracts structured fields from OCR results using templates.

    Handles:
    - Pattern matching for field detection
    - Value normalization (dates, currency, SSN, etc.)
    - Validation against expected formats
    - Confidence scoring
    """

    def __init__(self):
        self._normalizers = self._setup_normalizers()
        self._validators = self._setup_validators()

    def _setup_normalizers(self) -> Dict[FieldType, Callable]:
        """Setup normalizer functions for each field type."""
        return {
            FieldType.STRING: lambda x: x.strip() if x else "",
            FieldType.DECIMAL: self._normalize_decimal,
            FieldType.INTEGER: self._normalize_integer,
            FieldType.DATE: self._normalize_date,
            FieldType.SSN: self._normalize_ssn,
            FieldType.EIN: self._normalize_ein,
            FieldType.PHONE: self._normalize_phone,
            FieldType.ADDRESS: self._normalize_address,
            FieldType.BOOLEAN: self._normalize_boolean,
            FieldType.CURRENCY: self._normalize_currency,
        }

    def _setup_validators(self) -> Dict[FieldType, Callable]:
        """Setup validator functions for each field type."""
        return {
            FieldType.STRING: lambda x: True,
            FieldType.DECIMAL: self._validate_decimal,
            FieldType.INTEGER: self._validate_integer,
            FieldType.DATE: self._validate_date,
            FieldType.SSN: self._validate_ssn,
            FieldType.EIN: self._validate_ein,
            FieldType.PHONE: self._validate_phone,
            FieldType.ADDRESS: lambda x: bool(x),
            FieldType.BOOLEAN: lambda x: True,
            FieldType.CURRENCY: self._validate_currency,
        }

    def extract(
        self,
        ocr_result: OCRResult,
        templates: List[FieldTemplate]
    ) -> List[ExtractedField]:
        """
        Extract fields from OCR result using templates.

        Args:
            ocr_result: OCR processing result
            templates: List of field templates to extract

        Returns:
            List of extracted fields
        """
        extracted = []
        text = ocr_result.raw_text

        for template in templates:
            field = self._extract_field(text, template, ocr_result.confidence)
            if field:
                extracted.append(field)

        return extracted

    def _extract_field(
        self,
        text: str,
        template: FieldTemplate,
        base_confidence: float
    ) -> Optional[ExtractedField]:
        """Extract a single field using its template."""
        for pattern in template.patterns:
            match = pattern.search(text)
            if match:
                # Get the matched value
                if match.groups():
                    raw_value = match.group(1)
                else:
                    raw_value = match.group(0)

                # Normalize the value
                normalizer = template.normalizer or self._normalizers.get(
                    template.field_type,
                    lambda x: x
                )
                try:
                    normalized = normalizer(raw_value)
                except Exception:
                    normalized = raw_value

                # Validate the value
                validator = self._validators.get(template.field_type, lambda x: True)
                is_valid = validator(raw_value)
                validation_errors = []

                if not is_valid:
                    validation_errors.append(f"Invalid {template.field_type.value} format")

                # Run custom validators
                for custom_validator in template.validators:
                    try:
                        if not custom_validator(raw_value):
                            is_valid = False
                            validation_errors.append("Custom validation failed")
                    except Exception as e:
                        validation_errors.append(f"Validation error: {str(e)}")

                # Calculate confidence based on pattern match quality
                confidence = self._calculate_confidence(raw_value, template, base_confidence)

                return ExtractedField(
                    field_name=template.field_name,
                    field_label=template.field_label,
                    raw_value=raw_value,
                    normalized_value=normalized,
                    field_type=template.field_type,
                    confidence=confidence,
                    is_valid=is_valid,
                    validation_errors=validation_errors,
                    irs_reference=template.irs_reference,
                    target_table=template.target_table,
                    target_field=template.target_field,
                    box_number=template.box_number,
                )

        # Field not found
        if template.required:
            return ExtractedField(
                field_name=template.field_name,
                field_label=template.field_label,
                raw_value="",
                normalized_value=None,
                field_type=template.field_type,
                confidence=0.0,
                is_valid=False,
                validation_errors=["Required field not found"],
                irs_reference=template.irs_reference,
                target_table=template.target_table,
                target_field=template.target_field,
                box_number=template.box_number,
            )

        return None

    def _calculate_confidence(
        self,
        value: str,
        template: FieldTemplate,
        base_confidence: float
    ) -> float:
        """Calculate confidence score for an extracted field."""
        confidence = base_confidence

        # Adjust based on field type specifics
        if template.field_type == FieldType.SSN:
            if re.match(r'^\d{3}-\d{2}-\d{4}$', value):
                confidence += 10
            elif re.match(r'^\d{9}$', value):
                confidence += 5

        elif template.field_type == FieldType.EIN:
            if re.match(r'^\d{2}-\d{7}$', value):
                confidence += 10
            elif re.match(r'^\d{9}$', value):
                confidence += 5

        elif template.field_type in [FieldType.DECIMAL, FieldType.CURRENCY]:
            # Clean numeric value increases confidence
            cleaned = re.sub(r'[,$]', '', value)
            if re.match(r'^\d+\.?\d*$', cleaned):
                confidence += 10

        return min(100.0, confidence)

    # Normalizers
    def _normalize_decimal(self, value: str) -> Optional[Decimal]:
        """Normalize a decimal value."""
        try:
            cleaned = re.sub(r'[,$\s]', '', value)
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None

    def _normalize_integer(self, value: str) -> Optional[int]:
        """Normalize an integer value."""
        try:
            cleaned = re.sub(r'[,$\s]', '', value)
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None

    def _normalize_currency(self, value: str) -> Optional[Decimal]:
        """Normalize a currency value."""
        try:
            cleaned = re.sub(r'[$,\s]', '', value)
            return Decimal(cleaned).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            return None

    def _normalize_date(self, value: str) -> Optional[str]:
        """Normalize a date to YYYY-MM-DD format."""
        formats = [
            "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d",
            "%m/%d/%y", "%m-%d-%y",
            "%B %d, %Y", "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return value.strip()

    def _normalize_ssn(self, value: str) -> str:
        """Normalize SSN to XXX-XX-XXXX format."""
        digits = re.sub(r'\D', '', value)
        if len(digits) == 9:
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return value.strip()

    def _normalize_ein(self, value: str) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        digits = re.sub(r'\D', '', value)
        if len(digits) == 9:
            return f"{digits[:2]}-{digits[2:]}"
        return value.strip()

    def _normalize_phone(self, value: str) -> str:
        """Normalize phone to (XXX) XXX-XXXX format."""
        digits = re.sub(r'\D', '', value)
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        return value.strip()

    def _normalize_address(self, value: str) -> str:
        """Normalize address (basic cleanup)."""
        return ' '.join(value.split())

    def _normalize_boolean(self, value: str) -> bool:
        """Normalize boolean value."""
        lower = value.lower().strip()
        return lower in ['true', 'yes', '1', 'x', 'checked', 'y']

    # Validators
    def _validate_decimal(self, value: str) -> bool:
        """Validate decimal format."""
        try:
            cleaned = re.sub(r'[,$\s]', '', value)
            Decimal(cleaned)
            return True
        except (InvalidOperation, ValueError):
            return False

    def _validate_integer(self, value: str) -> bool:
        """Validate integer format."""
        try:
            cleaned = re.sub(r'[,$\s]', '', value)
            int(float(cleaned))
            return True
        except (ValueError, TypeError):
            return False

    def _validate_currency(self, value: str) -> bool:
        """Validate currency format."""
        return self._validate_decimal(value)

    def _validate_date(self, value: str) -> bool:
        """Validate date format."""
        formats = [
            "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d",
            "%m/%d/%y", "%m-%d-%y",
            "%B %d, %Y", "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                datetime.strptime(value.strip(), fmt)
                return True
            except ValueError:
                continue

        return False

    def _validate_ssn(self, value: str) -> bool:
        """Validate SSN format (XXX-XX-XXXX or 9 digits)."""
        digits = re.sub(r'\D', '', value)
        if len(digits) != 9:
            return False

        # Basic validation - not 000, 666, or 900-999 for first 3 digits
        first_three = int(digits[:3])
        if first_three in [0, 666] or 900 <= first_three <= 999:
            return False

        # Middle two digits can't be 00
        if digits[3:5] == '00':
            return False

        # Last four can't be 0000
        if digits[5:] == '0000':
            return False

        return True

    def _validate_ein(self, value: str) -> bool:
        """Validate EIN format (XX-XXXXXXX or 9 digits)."""
        digits = re.sub(r'\D', '', value)
        if len(digits) != 9:
            return False

        # First two digits should be valid campus codes
        valid_prefixes = [
            '10', '12', '20', '26', '27', '30', '32', '35', '36', '37',
            '38', '40', '41', '42', '43', '44', '45', '46', '47', '48',
            '50', '51', '52', '53', '54', '55', '56', '57', '58', '59',
            '60', '61', '62', '63', '64', '65', '66', '67', '68', '71',
            '72', '73', '74', '75', '76', '77', '80', '81', '82', '83',
            '84', '85', '86', '87', '88', '90', '91', '92', '93', '94',
            '95', '98', '99'
        ]

        return digits[:2] in valid_prefixes

    def _validate_phone(self, value: str) -> bool:
        """Validate US phone number."""
        digits = re.sub(r'\D', '', value)
        return len(digits) in [10, 11]


def create_w2_templates() -> List[FieldTemplate]:
    """Create field templates for W-2 form extraction."""
    return [
        FieldTemplate(
            field_name="employer_ein",
            field_label="Employer identification number (EIN)",
            field_type=FieldType.EIN,
            patterns=[
                r'(?:employer.*?(?:EIN|identification.*?number))[:\s]*(\d{2}[-\s]?\d{7})',
                r'(?:b\s+)?employer.*?identification.*?number.*?(\d{2}-\d{7})',
                r'EIN[:\s]*(\d{2}-?\d{7})',
            ],
            required=True,
            box_number="b",
            target_table="w2_records",
            target_field="employer_ein",
            irs_reference="Form W-2 Box b",
        ),
        FieldTemplate(
            field_name="employer_name",
            field_label="Employer's name, address, and ZIP code",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:employer[\'s]*\s+name)[,:\s]+([A-Za-z0-9\s.,&]+?)(?:\n|address)',
                r'(?:c\s+)?employer[\'s]*\s+name.*?address.*?zip.*?\n([^\n]+)',
            ],
            required=True,
            box_number="c",
            target_table="w2_records",
            target_field="employer_name",
            irs_reference="Form W-2 Box c",
        ),
        FieldTemplate(
            field_name="wages",
            field_label="Wages, tips, other compensation",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:wages.*?tips.*?compensation|box\s*1)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:1\s+)?wages.*?tips.*?other\s+comp.*?[:\s]+\$?([\d,]+\.?\d*)',
                r'\b1[.\s]+[\$]?([\d,]+\.\d{2})\b',
            ],
            required=True,
            box_number="1",
            target_table="w2_records",
            target_field="wages_tips_compensation",
            irs_reference="Form W-2 Box 1",
        ),
        FieldTemplate(
            field_name="federal_tax_withheld",
            field_label="Federal income tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:federal.*?income.*?tax.*?withheld|box\s*2)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:2\s+)?federal\s+income\s+tax\s+withheld[:\s]+\$?([\d,]+\.?\d*)',
                r'\b2[.\s]+[\$]?([\d,]+\.\d{2})\b',
            ],
            required=True,
            box_number="2",
            target_table="w2_records",
            target_field="federal_tax_withheld",
            irs_reference="Form W-2 Box 2",
        ),
        FieldTemplate(
            field_name="social_security_wages",
            field_label="Social security wages",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:social\s+security\s+wages|box\s*3)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:3\s+)?social\s+security\s+wages[:\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="3",
            target_table="w2_records",
            target_field="social_security_wages",
            irs_reference="Form W-2 Box 3",
        ),
        FieldTemplate(
            field_name="social_security_tax",
            field_label="Social security tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:social\s+security\s+tax.*?withheld|box\s*4)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:4\s+)?social\s+security\s+tax\s+withheld[:\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="4",
            target_table="w2_records",
            target_field="social_security_tax_withheld",
            irs_reference="Form W-2 Box 4",
        ),
        FieldTemplate(
            field_name="medicare_wages",
            field_label="Medicare wages and tips",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:medicare\s+wages.*?tips|box\s*5)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:5\s+)?medicare\s+wages\s+and\s+tips[:\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="5",
            target_table="w2_records",
            target_field="medicare_wages_tips",
            irs_reference="Form W-2 Box 5",
        ),
        FieldTemplate(
            field_name="medicare_tax",
            field_label="Medicare tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:medicare\s+tax.*?withheld|box\s*6)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:6\s+)?medicare\s+tax\s+withheld[:\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="6",
            target_table="w2_records",
            target_field="medicare_tax_withheld",
            irs_reference="Form W-2 Box 6",
        ),
        FieldTemplate(
            field_name="employee_ssn",
            field_label="Employee's social security number",
            field_type=FieldType.SSN,
            patterns=[
                r'(?:employee[\'s]*\s+)?(?:social\s+security\s+number|SSN)[:\s]*(\d{3}[-\s]?\d{2}[-\s]?\d{4})',
                r'(?:a\s+)?employee[\'s]*\s+social\s+security\s+number.*?(\d{3}-\d{2}-\d{4})',
                r'SSN[:\s]*(\d{3}-\d{2}-\d{4})',
            ],
            required=True,
            box_number="a",
            target_table="w2_records",
            target_field="employee_ssn",
            irs_reference="Form W-2 Box a",
        ),
        FieldTemplate(
            field_name="employee_name",
            field_label="Employee's name",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:e\s+)?employee[\'s]*\s+(?:first\s+)?name.*?\n([A-Za-z\s]+)',
                r'employee[\'s]*\s+name[:\s]+([A-Za-z\s]+)',
            ],
            required=True,
            box_number="e",
            target_table="w2_records",
            target_field="employee_name",
            irs_reference="Form W-2 Box e",
        ),
        FieldTemplate(
            field_name="state",
            field_label="State",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:15\s+)?(?:state)[:\s]+([A-Z]{2})',
                r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b',
            ],
            box_number="15",
            target_table="w2_records",
            target_field="state",
            irs_reference="Form W-2 Box 15",
        ),
        FieldTemplate(
            field_name="state_wages",
            field_label="State wages, tips, etc.",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:state\s+wages.*?tips|box\s*16)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:16\s+)?state\s+wages.*?[:\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="16",
            target_table="w2_records",
            target_field="state_wages",
            irs_reference="Form W-2 Box 16",
        ),
        FieldTemplate(
            field_name="state_tax",
            field_label="State income tax",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:state\s+income\s+tax|box\s*17)[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:17\s+)?state\s+income\s+tax[:\s]+\$?([\d,]+\.?\d*)',
            ],
            box_number="17",
            target_table="w2_records",
            target_field="state_tax_withheld",
            irs_reference="Form W-2 Box 17",
        ),
    ]


def create_1099_int_templates() -> List[FieldTemplate]:
    """Create field templates for 1099-INT form extraction."""
    return [
        FieldTemplate(
            field_name="payer_name",
            field_label="Payer's name",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:payer[\'s]*\s+name)[:\s]+([A-Za-z0-9\s.,&]+)',
                r'PAYER[\'S]*\s+(?:NAME|name)[:\s]+([^\n]+)',
            ],
            required=True,
            target_table="form_1099_int_records",
            target_field="payer_name",
            irs_reference="1099-INT Payer Info",
        ),
        FieldTemplate(
            field_name="payer_tin",
            field_label="Payer's TIN",
            field_type=FieldType.EIN,
            patterns=[
                r'(?:payer[\'s]*\s+TIN)[:\s]*(\d{2}[-\s]?\d{7})',
                r'PAYER[\'S]*\s+TIN[:\s]*(\d{2}-\d{7})',
            ],
            target_table="form_1099_int_records",
            target_field="payer_tin",
            irs_reference="1099-INT Payer TIN",
        ),
        FieldTemplate(
            field_name="interest_income",
            field_label="Interest income",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:1\s+)?interest\s+income[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:box\s*1)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="1",
            target_table="form_1099_int_records",
            target_field="interest_income",
            irs_reference="1099-INT Box 1",
        ),
        FieldTemplate(
            field_name="early_withdrawal_penalty",
            field_label="Early withdrawal penalty",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:2\s+)?early\s+withdrawal\s+penalty[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:box\s*2)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="2",
            target_table="form_1099_int_records",
            target_field="early_withdrawal_penalty",
            irs_reference="1099-INT Box 2",
        ),
        FieldTemplate(
            field_name="interest_on_savings_bonds",
            field_label="Interest on U.S. Savings Bonds",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:3\s+)?interest.*?(?:U\.?S\.?\s+)?savings\s+bonds[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="3",
            target_table="form_1099_int_records",
            target_field="interest_us_savings_bonds",
            irs_reference="1099-INT Box 3",
        ),
        FieldTemplate(
            field_name="federal_tax_withheld",
            field_label="Federal income tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:4\s+)?federal\s+income\s+tax\s+withheld[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="4",
            target_table="form_1099_int_records",
            target_field="federal_tax_withheld",
            irs_reference="1099-INT Box 4",
        ),
        FieldTemplate(
            field_name="tax_exempt_interest",
            field_label="Tax-exempt interest",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:8\s+)?tax[- ]exempt\s+interest[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="8",
            target_table="form_1099_int_records",
            target_field="tax_exempt_interest",
            irs_reference="1099-INT Box 8",
        ),
    ]


def create_1099_div_templates() -> List[FieldTemplate]:
    """Create field templates for 1099-DIV form extraction."""
    return [
        FieldTemplate(
            field_name="payer_name",
            field_label="Payer's name",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:payer[\'s]*\s+name)[:\s]+([A-Za-z0-9\s.,&]+)',
            ],
            required=True,
            target_table="form_1099_div_records",
            target_field="payer_name",
            irs_reference="1099-DIV Payer Info",
        ),
        FieldTemplate(
            field_name="ordinary_dividends",
            field_label="Total ordinary dividends",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:1a\s+)?(?:total\s+)?ordinary\s+dividends[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:box\s*1a)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="1a",
            target_table="form_1099_div_records",
            target_field="ordinary_dividends",
            irs_reference="1099-DIV Box 1a",
        ),
        FieldTemplate(
            field_name="qualified_dividends",
            field_label="Qualified dividends",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:1b\s+)?qualified\s+dividends[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:box\s*1b)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="1b",
            target_table="form_1099_div_records",
            target_field="qualified_dividends",
            irs_reference="1099-DIV Box 1b",
        ),
        FieldTemplate(
            field_name="capital_gain_distributions",
            field_label="Total capital gain distributions",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:2a\s+)?(?:total\s+)?capital\s+gain\s+(?:distr|dist)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="2a",
            target_table="form_1099_div_records",
            target_field="capital_gain_distributions",
            irs_reference="1099-DIV Box 2a",
        ),
        FieldTemplate(
            field_name="federal_tax_withheld",
            field_label="Federal income tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:4\s+)?federal\s+income\s+tax\s+withheld[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="4",
            target_table="form_1099_div_records",
            target_field="federal_tax_withheld",
            irs_reference="1099-DIV Box 4",
        ),
        FieldTemplate(
            field_name="nondividend_distributions",
            field_label="Nondividend distributions",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:3\s+)?nondividend\s+distributions[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="3",
            target_table="form_1099_div_records",
            target_field="nondividend_distributions",
            irs_reference="1099-DIV Box 3",
        ),
    ]


def create_1099_nec_templates() -> List[FieldTemplate]:
    """Create field templates for 1099-NEC form extraction."""
    return [
        FieldTemplate(
            field_name="payer_name",
            field_label="Payer's name",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:payer[\'s]*\s+name)[:\s]+([A-Za-z0-9\s.,&]+)',
            ],
            required=True,
            target_table="form_1099_nec_records",
            target_field="payer_name",
            irs_reference="1099-NEC Payer Info",
        ),
        FieldTemplate(
            field_name="payer_tin",
            field_label="Payer's TIN",
            field_type=FieldType.EIN,
            patterns=[
                r'(?:payer[\'s]*\s+TIN)[:\s]*(\d{2}[-\s]?\d{7})',
            ],
            target_table="form_1099_nec_records",
            target_field="payer_tin",
            irs_reference="1099-NEC Payer TIN",
        ),
        FieldTemplate(
            field_name="nonemployee_compensation",
            field_label="Nonemployee compensation",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:1\s+)?nonemployee\s+compensation[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:box\s*1)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            required=True,
            box_number="1",
            target_table="form_1099_nec_records",
            target_field="nonemployee_compensation",
            irs_reference="1099-NEC Box 1",
        ),
        FieldTemplate(
            field_name="federal_tax_withheld",
            field_label="Federal income tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:4\s+)?federal\s+income\s+tax\s+withheld[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="4",
            target_table="form_1099_nec_records",
            target_field="federal_tax_withheld",
            irs_reference="1099-NEC Box 4",
        ),
    ]


def create_1099_misc_templates() -> List[FieldTemplate]:
    """Create field templates for 1099-MISC form extraction."""
    return [
        FieldTemplate(
            field_name="payer_name",
            field_label="Payer's name",
            field_type=FieldType.STRING,
            patterns=[
                r'(?:payer[\'s]*\s+name)[:\s]+([A-Za-z0-9\s.,&]+)',
            ],
            required=True,
            target_table="form_1099_misc_records",
            target_field="payer_name",
            irs_reference="1099-MISC Payer Info",
        ),
        FieldTemplate(
            field_name="rents",
            field_label="Rents",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:1\s+)?rents[:\s]*\$?([\d,]+\.?\d*)',
                r'(?:box\s*1)[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="1",
            target_table="form_1099_misc_records",
            target_field="rents",
            irs_reference="1099-MISC Box 1",
        ),
        FieldTemplate(
            field_name="royalties",
            field_label="Royalties",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:2\s+)?royalties[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="2",
            target_table="form_1099_misc_records",
            target_field="royalties",
            irs_reference="1099-MISC Box 2",
        ),
        FieldTemplate(
            field_name="other_income",
            field_label="Other income",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:3\s+)?other\s+income[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="3",
            target_table="form_1099_misc_records",
            target_field="other_income",
            irs_reference="1099-MISC Box 3",
        ),
        FieldTemplate(
            field_name="federal_tax_withheld",
            field_label="Federal income tax withheld",
            field_type=FieldType.CURRENCY,
            patterns=[
                r'(?:4\s+)?federal\s+income\s+tax\s+withheld[:\s]*\$?([\d,]+\.?\d*)',
            ],
            box_number="4",
            target_table="form_1099_misc_records",
            target_field="federal_tax_withheld",
            irs_reference="1099-MISC Box 4",
        ),
    ]


# Template registry
DOCUMENT_TEMPLATES = {
    "w2": create_w2_templates,
    "1099-int": create_1099_int_templates,
    "1099-div": create_1099_div_templates,
    "1099-nec": create_1099_nec_templates,
    "1099-misc": create_1099_misc_templates,
}


def get_templates_for_document(document_type: str) -> List[FieldTemplate]:
    """Get field templates for a document type."""
    template_fn = DOCUMENT_TEMPLATES.get(document_type.lower())
    if template_fn:
        return template_fn()
    return []
