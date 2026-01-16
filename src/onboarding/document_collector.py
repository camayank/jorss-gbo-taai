"""Document Collector.

Manages collection and parsing of tax documents (W-2s, 1099s, etc.)
with OCR support and intelligent data extraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import re


class DocumentType(Enum):
    """Types of tax documents."""
    W2 = "W-2"
    W2G = "W-2G"
    W9 = "W-9"
    FORM_1099_NEC = "1099-NEC"
    FORM_1099_MISC = "1099-MISC"
    FORM_1099_INT = "1099-INT"
    FORM_1099_DIV = "1099-DIV"
    FORM_1099_B = "1099-B"
    FORM_1099_R = "1099-R"
    FORM_1099_G = "1099-G"
    FORM_1099_K = "1099-K"
    FORM_1098 = "1098"
    FORM_1098_E = "1098-E"
    FORM_1098_T = "1098-T"
    FORM_1095_A = "1095-A"
    FORM_1095_B = "1095-B"
    FORM_1095_C = "1095-C"
    SSA_1099 = "SSA-1099"
    SCHEDULE_K1 = "Schedule K-1"
    PROPERTY_TAX_STATEMENT = "Property Tax Statement"
    CHARITABLE_RECEIPT = "Charitable Receipt"
    MEDICAL_RECEIPT = "Medical Receipt"
    PRIOR_YEAR_RETURN = "Prior Year Return"
    STATE_ID = "State ID"
    DRIVERS_LICENSE = "Driver's License"
    OTHER = "Other"


class DocumentStatus(Enum):
    """Status of document processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    VERIFIED = "verified"
    ERROR = "error"


@dataclass
class SupportedDocument:
    """Information about a supported document type."""
    document_type: DocumentType
    name: str
    description: str
    common_issuers: List[str]
    required_for: List[str]  # Which income/deduction types
    key_fields: List[str]
    deadline: Optional[str] = None  # When issuers must provide
    help_text: Optional[str] = None


@dataclass
class ExtractedField:
    """A single extracted field from a document."""
    field_name: str
    box_number: Optional[str]
    raw_value: str
    parsed_value: Any
    confidence: float  # 0-100
    needs_review: bool = False
    validation_status: str = "pending"  # pending, valid, invalid
    irs_mapping: Optional[str] = None  # Where this maps on tax return


@dataclass
class ParsedDocument:
    """Result of parsing a tax document."""
    document_id: str
    document_type: DocumentType
    status: DocumentStatus
    filename: Optional[str] = None
    uploaded_at: Optional[str] = None
    processed_at: Optional[str] = None

    # Document metadata
    tax_year: Optional[int] = None
    issuer_name: Optional[str] = None
    issuer_ein: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_ssn: Optional[str] = None  # Masked

    # Extracted fields
    fields: Dict[str, ExtractedField] = field(default_factory=dict)

    # Quality metrics
    overall_confidence: float = 0.0
    fields_needing_review: List[str] = field(default_factory=list)
    extraction_warnings: List[str] = field(default_factory=list)

    # Raw data
    raw_text: Optional[str] = None
    image_quality_score: Optional[float] = None


class DocumentCollector:
    """
    Manages tax document collection and extraction.

    This class handles:
    - Document type identification
    - OCR and data extraction
    - Field validation
    - Mapping to tax return fields
    """

    # Document field mappings
    DOCUMENT_MAPPINGS = {
        DocumentType.W2: {
            "box_1": ("wages_tips", "income.w2_wages"),
            "box_2": ("federal_withheld", "income.federal_withholding"),
            "box_3": ("ss_wages", None),
            "box_4": ("ss_withheld", None),
            "box_5": ("medicare_wages", None),
            "box_6": ("medicare_withheld", None),
            "box_12d": ("retirement_contributions", "income.retirement_contributions_401k"),
            "box_16": ("state_wages", "income.state_wages"),
            "box_17": ("state_withheld", "income.state_withholding"),
        },
        DocumentType.FORM_1099_NEC: {
            "box_1": ("nonemployee_compensation", "income.self_employment_income"),
            "box_4": ("federal_withheld", "income.federal_withholding"),
        },
        DocumentType.FORM_1099_INT: {
            "box_1": ("interest_income", "income.interest_income"),
            "box_3": ("interest_savings_bonds", None),
            "box_4": ("federal_withheld", None),
        },
        DocumentType.FORM_1099_DIV: {
            "box_1a": ("total_dividends", "income.dividend_income"),
            "box_1b": ("qualified_dividends", "income.qualified_dividends"),
            "box_2a": ("capital_gain_distributions", None),
            "box_4": ("federal_withheld", None),
            "box_7": ("foreign_tax_paid", "income.foreign_taxes_paid"),
        },
        DocumentType.FORM_1099_B: {
            "proceeds": ("gross_proceeds", None),
            "cost_basis": ("cost_basis", None),
            "gain_loss": ("gain_loss", "income.capital_gain_income"),
        },
        DocumentType.FORM_1099_R: {
            "box_1": ("gross_distribution", None),
            "box_2a": ("taxable_amount", "income.retirement_income"),
            "box_4": ("federal_withheld", None),
            "box_7": ("distribution_code", None),
        },
        DocumentType.FORM_1098: {
            "box_1": ("mortgage_interest", "deductions.mortgage_interest"),
            "box_2": ("outstanding_principal", None),
            "box_5": ("mortgage_insurance", None),
            "box_6": ("points_paid", "deductions.mortgage_points"),
        },
        DocumentType.FORM_1098_E: {
            "box_1": ("student_loan_interest", "income.student_loan_interest"),
        },
        DocumentType.FORM_1098_T: {
            "box_1": ("payments_received", "credits.education_expenses"),
            "box_5": ("scholarships_grants", None),
        },
        DocumentType.SSA_1099: {
            "box_5": ("net_benefits", "income.social_security_income"),
        },
    }

    # Supported documents with metadata
    SUPPORTED_DOCUMENTS: Dict[DocumentType, SupportedDocument] = {
        DocumentType.W2: SupportedDocument(
            document_type=DocumentType.W2,
            name="Form W-2",
            description="Wage and Tax Statement from your employer",
            common_issuers=["Employers"],
            required_for=["W-2 income"],
            key_fields=["wages", "federal_withheld", "state_withheld"],
            deadline="January 31",
            help_text="Your employer must provide this by January 31. Check your mail or employer portal.",
        ),
        DocumentType.FORM_1099_NEC: SupportedDocument(
            document_type=DocumentType.FORM_1099_NEC,
            name="Form 1099-NEC",
            description="Nonemployee Compensation (freelance/contract income)",
            common_issuers=["Clients", "Companies you contracted with"],
            required_for=["1099 income", "Self-employment"],
            key_fields=["nonemployee_compensation"],
            deadline="January 31",
            help_text="Received from clients who paid you $600+ for services.",
        ),
        DocumentType.FORM_1099_INT: SupportedDocument(
            document_type=DocumentType.FORM_1099_INT,
            name="Form 1099-INT",
            description="Interest Income from banks and investments",
            common_issuers=["Banks", "Credit unions", "Brokerages"],
            required_for=["Investment income"],
            key_fields=["interest_income"],
            deadline="January 31",
            help_text="Shows interest earned on savings accounts, CDs, bonds.",
        ),
        DocumentType.FORM_1099_DIV: SupportedDocument(
            document_type=DocumentType.FORM_1099_DIV,
            name="Form 1099-DIV",
            description="Dividends and Distributions from investments",
            common_issuers=["Brokerages", "Mutual funds"],
            required_for=["Investment income"],
            key_fields=["total_dividends", "qualified_dividends", "foreign_tax_paid"],
            deadline="January 31",
            help_text="Shows dividends from stocks and mutual funds.",
        ),
        DocumentType.FORM_1099_B: SupportedDocument(
            document_type=DocumentType.FORM_1099_B,
            name="Form 1099-B",
            description="Proceeds from Broker and Barter Exchange",
            common_issuers=["Brokerages"],
            required_for=["Investment income", "Stock sales"],
            key_fields=["proceeds", "cost_basis", "gain_loss"],
            deadline="February 15",
            help_text="Reports sales of stocks, bonds, mutual funds.",
        ),
        DocumentType.FORM_1099_R: SupportedDocument(
            document_type=DocumentType.FORM_1099_R,
            name="Form 1099-R",
            description="Distributions from Pensions, IRAs, etc.",
            common_issuers=["401(k) administrators", "IRA custodians", "Pension plans"],
            required_for=["Retirement income"],
            key_fields=["gross_distribution", "taxable_amount"],
            deadline="January 31",
            help_text="Shows distributions from retirement accounts.",
        ),
        DocumentType.FORM_1098: SupportedDocument(
            document_type=DocumentType.FORM_1098,
            name="Form 1098",
            description="Mortgage Interest Statement",
            common_issuers=["Mortgage lenders"],
            required_for=["Mortgage interest deduction"],
            key_fields=["mortgage_interest", "points_paid"],
            deadline="January 31",
            help_text="Shows mortgage interest paid to your lender.",
        ),
        DocumentType.FORM_1098_T: SupportedDocument(
            document_type=DocumentType.FORM_1098_T,
            name="Form 1098-T",
            description="Tuition Statement from educational institutions",
            common_issuers=["Colleges", "Universities"],
            required_for=["Education credits"],
            key_fields=["payments_received", "scholarships"],
            deadline="January 31",
            help_text="Required for education credits (AOTC, LLC).",
        ),
        DocumentType.FORM_1095_A: SupportedDocument(
            document_type=DocumentType.FORM_1095_A,
            name="Form 1095-A",
            description="Health Insurance Marketplace Statement",
            common_issuers=["Healthcare.gov", "State marketplaces"],
            required_for=["Premium Tax Credit"],
            key_fields=["monthly_premiums", "advance_ptc"],
            deadline="January 31",
            help_text="If you had Marketplace insurance, you must reconcile PTC.",
        ),
        DocumentType.SSA_1099: SupportedDocument(
            document_type=DocumentType.SSA_1099,
            name="Form SSA-1099",
            description="Social Security Benefit Statement",
            common_issuers=["Social Security Administration"],
            required_for=["Social Security income"],
            key_fields=["net_benefits"],
            deadline="January 31",
            help_text="Shows your Social Security benefits for the year.",
        ),
    }

    def __init__(self):
        """Initialize the document collector."""
        self._documents: Dict[str, ParsedDocument] = {}
        self._document_counter = 0

    def get_expected_documents(self, profile: Any) -> List[SupportedDocument]:
        """Get list of expected documents based on taxpayer profile."""
        expected = []

        if hasattr(profile, 'has_w2_income') and profile.has_w2_income:
            expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.W2])

        if hasattr(profile, 'income_sources'):
            if "1099_nec" in profile.income_sources:
                expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.FORM_1099_NEC])

            if "investments" in profile.income_sources:
                expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.FORM_1099_INT])
                expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.FORM_1099_DIV])
                expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.FORM_1099_B])

            if "retirement" in profile.income_sources:
                expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.FORM_1099_R])
                expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.SSA_1099])

        if hasattr(profile, 'has_mortgage_interest') and profile.has_mortgage_interest:
            expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.FORM_1098])

        if hasattr(profile, 'potential_education') and profile.potential_education:
            expected.append(self.SUPPORTED_DOCUMENTS[DocumentType.FORM_1098_T])

        return expected

    def identify_document_type(self, text: str) -> Tuple[DocumentType, float]:
        """
        Identify document type from extracted text.

        Returns tuple of (DocumentType, confidence).
        """
        text_lower = text.lower()

        # Check for specific form patterns
        patterns = [
            (r"w-2\s+wage", DocumentType.W2),
            (r"form\s*w-2", DocumentType.W2),
            (r"1099-nec", DocumentType.FORM_1099_NEC),
            (r"nonemployee\s+compensation", DocumentType.FORM_1099_NEC),
            (r"1099-int", DocumentType.FORM_1099_INT),
            (r"interest\s+income", DocumentType.FORM_1099_INT),
            (r"1099-div", DocumentType.FORM_1099_DIV),
            (r"dividends\s+and\s+distributions", DocumentType.FORM_1099_DIV),
            (r"1099-b", DocumentType.FORM_1099_B),
            (r"proceeds\s+from\s+broker", DocumentType.FORM_1099_B),
            (r"1099-r", DocumentType.FORM_1099_R),
            (r"distributions\s+from\s+pensions", DocumentType.FORM_1099_R),
            (r"form\s*1098\b", DocumentType.FORM_1098),
            (r"mortgage\s+interest\s+statement", DocumentType.FORM_1098),
            (r"1098-t", DocumentType.FORM_1098_T),
            (r"tuition\s+statement", DocumentType.FORM_1098_T),
            (r"1098-e", DocumentType.FORM_1098_E),
            (r"student\s+loan\s+interest", DocumentType.FORM_1098_E),
            (r"1095-a", DocumentType.FORM_1095_A),
            (r"health\s+insurance\s+marketplace", DocumentType.FORM_1095_A),
            (r"ssa-1099", DocumentType.SSA_1099),
            (r"social\s+security\s+benefit", DocumentType.SSA_1099),
        ]

        for pattern, doc_type in patterns:
            if re.search(pattern, text_lower):
                return (doc_type, 95.0)

        return (DocumentType.OTHER, 20.0)

    def parse_document(
        self,
        document_id: str,
        document_type: DocumentType,
        raw_text: str,
        filename: Optional[str] = None
    ) -> ParsedDocument:
        """
        Parse a document and extract relevant fields.

        This is a simplified parser - in production would use OCR + ML.
        """
        doc = ParsedDocument(
            document_id=document_id,
            document_type=document_type,
            status=DocumentStatus.PROCESSING,
            filename=filename,
            uploaded_at=datetime.now().isoformat(),
        )

        # Get field mappings for this document type
        mappings = self.DOCUMENT_MAPPINGS.get(document_type, {})

        # Extract fields based on document type
        if document_type == DocumentType.W2:
            doc = self._parse_w2(doc, raw_text)
        elif document_type == DocumentType.FORM_1099_NEC:
            doc = self._parse_1099_nec(doc, raw_text)
        elif document_type == DocumentType.FORM_1099_INT:
            doc = self._parse_1099_int(doc, raw_text)
        elif document_type == DocumentType.FORM_1099_DIV:
            doc = self._parse_1099_div(doc, raw_text)
        elif document_type == DocumentType.FORM_1098:
            doc = self._parse_1098(doc, raw_text)
        elif document_type == DocumentType.SSA_1099:
            doc = self._parse_ssa_1099(doc, raw_text)
        else:
            doc = self._parse_generic(doc, raw_text)

        # Calculate overall confidence
        if doc.fields:
            confidences = [f.confidence for f in doc.fields.values()]
            doc.overall_confidence = sum(confidences) / len(confidences)

        # Identify fields needing review
        doc.fields_needing_review = [
            name for name, f in doc.fields.items()
            if f.confidence < 80 or f.needs_review
        ]

        doc.status = DocumentStatus.EXTRACTED
        doc.processed_at = datetime.now().isoformat()
        doc.raw_text = raw_text

        self._documents[document_id] = doc
        return doc

    def _parse_w2(self, doc: ParsedDocument, text: str) -> ParsedDocument:
        """Parse W-2 form."""
        # Extract employer info
        ein_match = re.search(r"employer.*?(\d{2}-\d{7})", text, re.IGNORECASE)
        if ein_match:
            doc.issuer_ein = ein_match.group(1)

        # Extract boxes using common patterns
        patterns = {
            "box_1": r"(?:box\s*1|wages.*?tips).*?\$?\s*([\d,]+\.?\d*)",
            "box_2": r"(?:box\s*2|federal.*?withheld).*?\$?\s*([\d,]+\.?\d*)",
            "box_3": r"(?:box\s*3|social\s*security\s*wages).*?\$?\s*([\d,]+\.?\d*)",
            "box_4": r"(?:box\s*4|social\s*security.*?withheld).*?\$?\s*([\d,]+\.?\d*)",
            "box_5": r"(?:box\s*5|medicare\s*wages).*?\$?\s*([\d,]+\.?\d*)",
            "box_16": r"(?:box\s*16|state\s*wages).*?\$?\s*([\d,]+\.?\d*)",
            "box_17": r"(?:box\s*17|state.*?withheld).*?\$?\s*([\d,]+\.?\d*)",
        }

        mappings = self.DOCUMENT_MAPPINGS[DocumentType.W2]

        for box, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                parsed = self._parse_currency(raw_value)
                mapping = mappings.get(box, (box, None))

                doc.fields[box] = ExtractedField(
                    field_name=mapping[0],
                    box_number=box.replace("box_", "Box "),
                    raw_value=raw_value,
                    parsed_value=parsed,
                    confidence=85.0 if parsed else 50.0,
                    irs_mapping=mapping[1],
                )

        return doc

    def _parse_1099_nec(self, doc: ParsedDocument, text: str) -> ParsedDocument:
        """Parse 1099-NEC form."""
        patterns = {
            "box_1": r"(?:box\s*1|nonemployee\s*compensation).*?\$?\s*([\d,]+\.?\d*)",
            "box_4": r"(?:box\s*4|federal.*?withheld).*?\$?\s*([\d,]+\.?\d*)",
        }

        mappings = self.DOCUMENT_MAPPINGS[DocumentType.FORM_1099_NEC]

        for box, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                parsed = self._parse_currency(raw_value)
                mapping = mappings.get(box, (box, None))

                doc.fields[box] = ExtractedField(
                    field_name=mapping[0],
                    box_number=box.replace("box_", "Box "),
                    raw_value=raw_value,
                    parsed_value=parsed,
                    confidence=85.0 if parsed else 50.0,
                    irs_mapping=mapping[1],
                )

        return doc

    def _parse_1099_int(self, doc: ParsedDocument, text: str) -> ParsedDocument:
        """Parse 1099-INT form."""
        patterns = {
            "box_1": r"(?:box\s*1|interest\s*income).*?\$?\s*([\d,]+\.?\d*)",
        }

        mappings = self.DOCUMENT_MAPPINGS[DocumentType.FORM_1099_INT]

        for box, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                parsed = self._parse_currency(raw_value)
                mapping = mappings.get(box, (box, None))

                doc.fields[box] = ExtractedField(
                    field_name=mapping[0],
                    box_number=box.replace("box_", "Box "),
                    raw_value=raw_value,
                    parsed_value=parsed,
                    confidence=85.0 if parsed else 50.0,
                    irs_mapping=mapping[1],
                )

        return doc

    def _parse_1099_div(self, doc: ParsedDocument, text: str) -> ParsedDocument:
        """Parse 1099-DIV form."""
        patterns = {
            "box_1a": r"(?:box\s*1a|total.*?dividends).*?\$?\s*([\d,]+\.?\d*)",
            "box_1b": r"(?:box\s*1b|qualified.*?dividends).*?\$?\s*([\d,]+\.?\d*)",
            "box_7": r"(?:box\s*7|foreign\s*tax).*?\$?\s*([\d,]+\.?\d*)",
        }

        mappings = self.DOCUMENT_MAPPINGS[DocumentType.FORM_1099_DIV]

        for box, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                parsed = self._parse_currency(raw_value)
                mapping = mappings.get(box, (box, None))

                doc.fields[box] = ExtractedField(
                    field_name=mapping[0],
                    box_number=box.replace("box_", "Box "),
                    raw_value=raw_value,
                    parsed_value=parsed,
                    confidence=85.0 if parsed else 50.0,
                    irs_mapping=mapping[1],
                )

        return doc

    def _parse_1098(self, doc: ParsedDocument, text: str) -> ParsedDocument:
        """Parse 1098 form."""
        patterns = {
            "box_1": r"(?:box\s*1|mortgage\s*interest).*?\$?\s*([\d,]+\.?\d*)",
            "box_6": r"(?:box\s*6|points\s*paid).*?\$?\s*([\d,]+\.?\d*)",
        }

        mappings = self.DOCUMENT_MAPPINGS[DocumentType.FORM_1098]

        for box, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                parsed = self._parse_currency(raw_value)
                mapping = mappings.get(box, (box, None))

                doc.fields[box] = ExtractedField(
                    field_name=mapping[0],
                    box_number=box.replace("box_", "Box "),
                    raw_value=raw_value,
                    parsed_value=parsed,
                    confidence=85.0 if parsed else 50.0,
                    irs_mapping=mapping[1],
                )

        return doc

    def _parse_ssa_1099(self, doc: ParsedDocument, text: str) -> ParsedDocument:
        """Parse SSA-1099 form."""
        patterns = {
            "box_5": r"(?:box\s*5|net\s*benefits).*?\$?\s*([\d,]+\.?\d*)",
        }

        mappings = self.DOCUMENT_MAPPINGS[DocumentType.SSA_1099]

        for box, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_value = match.group(1)
                parsed = self._parse_currency(raw_value)
                mapping = mappings.get(box, (box, None))

                doc.fields[box] = ExtractedField(
                    field_name=mapping[0],
                    box_number=box.replace("box_", "Box "),
                    raw_value=raw_value,
                    parsed_value=parsed,
                    confidence=85.0 if parsed else 50.0,
                    irs_mapping=mapping[1],
                )

        return doc

    def _parse_generic(self, doc: ParsedDocument, text: str) -> ParsedDocument:
        """Generic document parser for unrecognized types."""
        # Try to find any dollar amounts
        amounts = re.findall(r"\$\s*([\d,]+\.?\d*)", text)
        for i, amount in enumerate(amounts[:5]):  # Limit to first 5
            parsed = self._parse_currency(amount)
            doc.fields[f"amount_{i + 1}"] = ExtractedField(
                field_name=f"Amount {i + 1}",
                box_number=None,
                raw_value=amount,
                parsed_value=parsed,
                confidence=50.0,
                needs_review=True,
            )

        doc.extraction_warnings.append(
            "Document type not fully recognized. Please verify extracted values."
        )
        return doc

    def _parse_currency(self, value: str) -> Optional[float]:
        """Parse currency string to float."""
        try:
            cleaned = value.replace(",", "").replace("$", "").strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return None

    def get_document(self, document_id: str) -> Optional[ParsedDocument]:
        """Get a parsed document by ID."""
        return self._documents.get(document_id)

    def get_all_documents(self) -> List[ParsedDocument]:
        """Get all parsed documents."""
        return list(self._documents.values())

    def generate_document_id(self) -> str:
        """Generate a unique document ID."""
        self._document_counter += 1
        return f"DOC-{datetime.now().strftime('%Y%m%d')}-{self._document_counter:04d}"

    def export_to_tax_data(self) -> Dict[str, Any]:
        """Export all document data to tax return format."""
        tax_data = {
            "income": {},
            "deductions": {},
            "credits": {},
        }

        for doc in self._documents.values():
            for field in doc.fields.values():
                if field.irs_mapping and field.parsed_value is not None:
                    parts = field.irs_mapping.split(".")
                    if len(parts) == 2:
                        category, field_name = parts
                        if category in tax_data:
                            # Sum up values if field already exists
                            current = tax_data[category].get(field_name, 0.0)
                            tax_data[category][field_name] = current + field.parsed_value

        return tax_data

    def get_missing_documents(self, expected: List[SupportedDocument]) -> List[SupportedDocument]:
        """Get list of expected documents that haven't been uploaded."""
        uploaded_types = {doc.document_type for doc in self._documents.values()}
        return [d for d in expected if d.document_type not in uploaded_types]
