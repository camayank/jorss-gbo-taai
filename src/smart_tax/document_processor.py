"""
Smart Document Processor

Processes uploaded tax documents with real-time feedback:
- Instant confidence scoring
- Progressive field extraction
- Cross-document validation
- Immediate estimate updates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from decimal import Decimal
import re

from src.services.ocr.confidence_scorer import (
    ConfidenceScorer,
    ConfidenceResult,
    ConfidenceLevel,
    ConfidenceFactors,
    DocumentConfidenceAggregator,
)
from src.services.ocr.inference_engine import (
    FieldInferenceEngine,
    InferenceResult,
    MultiDocumentInference,
)


class DocumentType(str, Enum):
    """Supported tax document types."""
    W2 = "w2"
    W2_G = "w2_g"
    FORM_1099_NEC = "1099_nec"
    FORM_1099_MISC = "1099_misc"
    FORM_1099_INT = "1099_int"
    FORM_1099_DIV = "1099_div"
    FORM_1099_B = "1099_b"
    FORM_1099_R = "1099_r"
    FORM_1099_G = "1099_g"
    FORM_1099_SA = "1099_sa"
    FORM_1098 = "1098"
    FORM_1098_T = "1098_t"
    FORM_1098_E = "1098_e"
    SCHEDULE_K1 = "k1"
    UNKNOWN = "unknown"


@dataclass
class ExtractedField:
    """A single extracted field with confidence."""
    name: str
    raw_value: str
    normalized_value: Any
    confidence: ConfidenceResult
    source_location: Optional[Dict[str, int]] = None  # x, y, width, height

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence.to_dict(),
            "source_location": self.source_location,
        }


@dataclass
class ProcessedDocument:
    """Result of processing a tax document."""
    document_id: str
    document_type: DocumentType
    tax_year: int
    fields: List[ExtractedField]
    overall_confidence: float
    confidence_level: ConfidenceLevel
    inference_result: Optional[InferenceResult] = None
    warnings: List[str] = field(default_factory=list)
    needs_review: bool = False
    review_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_type": self.document_type.value,
            "tax_year": self.tax_year,
            "fields": [f.to_dict() for f in self.fields],
            "overall_confidence": self.overall_confidence,
            "confidence_level": self.confidence_level.value,
            "inference_result": self.inference_result.to_dict() if self.inference_result else None,
            "warnings": self.warnings,
            "needs_review": self.needs_review,
            "review_reasons": self.review_reasons,
        }

    def get_field(self, name: str) -> Optional[ExtractedField]:
        """Get a specific field by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def get_field_value(self, name: str, default: Any = None) -> Any:
        """Get normalized value of a field."""
        field = self.get_field(name)
        return field.normalized_value if field else default


@dataclass
class DocumentSummary:
    """Summary of a processed document for display."""
    document_type: str
    description: str
    key_amount: Decimal
    key_amount_label: str
    confidence_level: str
    field_count: int
    needs_review: bool
    icon: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_type": self.document_type,
            "description": self.description,
            "key_amount": float(self.key_amount),
            "key_amount_label": self.key_amount_label,
            "confidence_level": self.confidence_level,
            "field_count": self.field_count,
            "needs_review": self.needs_review,
            "icon": self.icon,
        }


class SmartDocumentProcessor:
    """
    Processes tax documents with intelligent extraction and validation.

    Provides:
    - Real-time confidence scoring
    - Field inference for missing data
    - Cross-document validation
    - User-friendly summaries
    """

    # Document type metadata
    DOCUMENT_META = {
        DocumentType.W2: {
            "description": "Wage and Tax Statement",
            "key_field": "wages",
            "key_label": "Wages",
            "icon": "briefcase",
        },
        DocumentType.FORM_1099_NEC: {
            "description": "Nonemployee Compensation",
            "key_field": "nonemployee_compensation",
            "key_label": "Self-Employment Income",
            "icon": "user-tie",
        },
        DocumentType.FORM_1099_INT: {
            "description": "Interest Income",
            "key_field": "interest_income",
            "key_label": "Interest",
            "icon": "piggy-bank",
        },
        DocumentType.FORM_1099_DIV: {
            "description": "Dividend Income",
            "key_field": "ordinary_dividends",
            "key_label": "Dividends",
            "icon": "chart-line",
        },
        DocumentType.FORM_1099_B: {
            "description": "Broker Statement",
            "key_field": "proceeds",
            "key_label": "Sales Proceeds",
            "icon": "exchange-alt",
        },
        DocumentType.FORM_1099_R: {
            "description": "Retirement Distribution",
            "key_field": "gross_distribution",
            "key_label": "Distribution",
            "icon": "umbrella-beach",
        },
        DocumentType.FORM_1099_G: {
            "description": "Government Payment",
            "key_field": "unemployment_compensation",
            "key_label": "Unemployment",
            "icon": "landmark",
        },
        DocumentType.FORM_1098: {
            "description": "Mortgage Interest",
            "key_field": "mortgage_interest",
            "key_label": "Interest Paid",
            "icon": "home",
        },
        DocumentType.FORM_1098_T: {
            "description": "Tuition Statement",
            "key_field": "amounts_billed",
            "key_label": "Tuition",
            "icon": "graduation-cap",
        },
    }

    # Required fields by document type
    REQUIRED_FIELDS = {
        DocumentType.W2: ["wages", "federal_tax_withheld", "employer_ein"],
        DocumentType.FORM_1099_NEC: ["nonemployee_compensation", "payer_tin"],
        DocumentType.FORM_1099_INT: ["interest_income", "payer_tin"],
        DocumentType.FORM_1099_DIV: ["ordinary_dividends", "payer_tin"],
    }

    def __init__(self, tax_year: int = 2024):
        self.tax_year = tax_year
        self.confidence_scorer = ConfidenceScorer()
        self.inference_engine = FieldInferenceEngine(tax_year=tax_year)
        self.aggregator = DocumentConfidenceAggregator()
        self.multi_doc_inference = MultiDocumentInference(tax_year=tax_year)

    def process_document(
        self,
        document_id: str,
        document_type: str,
        raw_extraction: Dict[str, Any],
        ocr_confidence: float = 0.85,
    ) -> ProcessedDocument:
        """
        Process a single document with confidence scoring and inference.

        Args:
            document_id: Unique identifier for this document
            document_type: Type of tax document (w2, 1099_nec, etc.)
            raw_extraction: Raw extracted fields from OCR
            ocr_confidence: Overall OCR confidence (0-1)

        Returns:
            ProcessedDocument with scored fields and inferences
        """
        doc_type = self._normalize_document_type(document_type)

        # Score each extracted field
        extracted_fields = []
        field_scores = {}

        for field_name, raw_value in raw_extraction.items():
            if raw_value is None:
                continue

            # Normalize the value
            normalized = self._normalize_value(field_name, raw_value)

            # Get related fields for cross-validation
            related_fields = {k: v for k, v in raw_extraction.items() if k != field_name}

            # Calculate confidence
            confidence = self.confidence_scorer.calculate_confidence(
                field_name=field_name,
                raw_value=str(raw_value),
                normalized_value=normalized,
                ocr_confidence=ocr_confidence,
                field_type=self._get_field_type(field_name),
                related_fields=related_fields,
            )

            extracted_fields.append(ExtractedField(
                name=field_name,
                raw_value=str(raw_value),
                normalized_value=normalized,
                confidence=confidence,
            ))

            field_scores[field_name] = confidence.overall_score

        # Run inference to fill missing fields and validate
        inference_result = self.inference_engine.infer_and_validate(
            document_type=doc_type.value,
            extracted_fields={f.name: f.normalized_value for f in extracted_fields},
        )

        # Add inferred fields
        for inferred in inference_result.inferred_fields:
            # Check if field already exists
            existing = next((f for f in extracted_fields if f.name == inferred.field_name), None)
            if not existing:
                inferred_score = inferred.confidence * 100
                inferred_level = ConfidenceLevel.MEDIUM if inferred.confidence > 0.7 else ConfidenceLevel.LOW
                extracted_fields.append(ExtractedField(
                    name=inferred.field_name,
                    raw_value=f"[Inferred: {inferred.inferred_value}]",
                    normalized_value=inferred.inferred_value,
                    confidence=ConfidenceResult(
                        overall_score=inferred_score,
                        level=inferred_level,
                        factors=ConfidenceFactors(
                            ocr_quality=0,
                            format_match=inferred_score,
                            pattern_strength=inferred_score,
                            cross_field_consistency=inferred_score,
                            positional_accuracy=0,
                            value_plausibility=inferred_score,
                        ),
                        needs_verification=True,
                        verification_reason=inferred.explanation,
                        suggestions=[f"Inferred value - please verify: {inferred.explanation}"],
                    ),
                ))

        # Calculate overall confidence
        if field_scores:
            overall_confidence = sum(field_scores.values()) / len(field_scores)
        else:
            overall_confidence = 50.0

        # Determine confidence level
        if overall_confidence >= 85:
            confidence_level = ConfidenceLevel.HIGH
        elif overall_confidence >= 70:
            confidence_level = ConfidenceLevel.MEDIUM
        else:
            confidence_level = ConfidenceLevel.LOW

        # Check for review needs
        needs_review, review_reasons = self._check_review_needed(
            doc_type, extracted_fields, inference_result, overall_confidence
        )

        # Collect warnings
        warnings = []
        for issue in inference_result.validation_issues:
            warnings.append(f"{issue.field_name}: {issue.message}")

        return ProcessedDocument(
            document_id=document_id,
            document_type=doc_type,
            tax_year=self.tax_year,
            fields=extracted_fields,
            overall_confidence=overall_confidence,
            confidence_level=confidence_level,
            inference_result=inference_result,
            warnings=warnings,
            needs_review=needs_review,
            review_reasons=review_reasons,
        )

    def get_document_summary(self, document: ProcessedDocument) -> DocumentSummary:
        """Generate a user-friendly summary of a processed document."""
        meta = self.DOCUMENT_META.get(document.document_type, {
            "description": "Tax Document",
            "key_field": None,
            "key_label": "Amount",
            "icon": "file-alt",
        })

        # Get key amount
        key_amount = Decimal("0")
        if meta.get("key_field"):
            key_amount = Decimal(str(document.get_field_value(meta["key_field"], 0) or 0))

        return DocumentSummary(
            document_type=document.document_type.value,
            description=meta["description"],
            key_amount=key_amount,
            key_amount_label=meta["key_label"],
            confidence_level=document.confidence_level.value,
            field_count=len(document.fields),
            needs_review=document.needs_review,
            icon=meta["icon"],
        )

    def aggregate_documents(
        self,
        documents: List[ProcessedDocument],
    ) -> Dict[str, Any]:
        """
        Aggregate data from multiple documents.

        Returns combined income, withholding, and other aggregated values.
        """
        aggregated = {
            "total_wages": Decimal("0"),
            "total_federal_withheld": Decimal("0"),
            "total_state_withheld": Decimal("0"),
            "total_interest_income": Decimal("0"),
            "total_dividend_income": Decimal("0"),
            "total_self_employment": Decimal("0"),
            "total_retirement_distributions": Decimal("0"),
            "documents_by_type": {},
            "overall_confidence": 0.0,
            "needs_review": False,
            "review_reasons": [],
        }

        confidence_scores = []

        for doc in documents:
            # Track document counts by type
            doc_type = doc.document_type.value
            if doc_type not in aggregated["documents_by_type"]:
                aggregated["documents_by_type"][doc_type] = 0
            aggregated["documents_by_type"][doc_type] += 1

            # Aggregate values based on document type
            if doc.document_type == DocumentType.W2:
                aggregated["total_wages"] += Decimal(str(doc.get_field_value("wages", 0) or 0))
                aggregated["total_federal_withheld"] += Decimal(str(
                    doc.get_field_value("federal_tax_withheld", 0) or 0
                ))
                aggregated["total_state_withheld"] += Decimal(str(
                    doc.get_field_value("state_tax_withheld", 0) or 0
                ))
            elif doc.document_type == DocumentType.FORM_1099_INT:
                aggregated["total_interest_income"] += Decimal(str(
                    doc.get_field_value("interest_income", 0) or 0
                ))
            elif doc.document_type == DocumentType.FORM_1099_DIV:
                aggregated["total_dividend_income"] += Decimal(str(
                    doc.get_field_value("ordinary_dividends", 0) or 0
                ))
            elif doc.document_type == DocumentType.FORM_1099_NEC:
                aggregated["total_self_employment"] += Decimal(str(
                    doc.get_field_value("nonemployee_compensation", 0) or 0
                ))
            elif doc.document_type == DocumentType.FORM_1099_R:
                aggregated["total_retirement_distributions"] += Decimal(str(
                    doc.get_field_value("gross_distribution", 0) or 0
                ))

            confidence_scores.append(doc.overall_confidence)

            if doc.needs_review:
                aggregated["needs_review"] = True
                aggregated["review_reasons"].extend(doc.review_reasons)

        # Calculate overall confidence
        if confidence_scores:
            aggregated["overall_confidence"] = sum(confidence_scores) / len(confidence_scores)

        # Calculate total income
        aggregated["total_income"] = (
            aggregated["total_wages"] +
            aggregated["total_interest_income"] +
            aggregated["total_dividend_income"] +
            aggregated["total_self_employment"] +
            aggregated["total_retirement_distributions"]
        )

        # Convert Decimals to floats for JSON serialization
        for key, value in aggregated.items():
            if isinstance(value, Decimal):
                aggregated[key] = float(value)

        return aggregated

    def validate_cross_document(
        self,
        documents: List[ProcessedDocument],
    ) -> List[Dict[str, Any]]:
        """
        Validate consistency across multiple documents.

        Returns list of potential issues found.
        """
        issues = []

        # Check for duplicate documents
        seen_employers = {}
        for doc in documents:
            if doc.document_type == DocumentType.W2:
                ein = doc.get_field_value("employer_ein")
                if ein:
                    if ein in seen_employers:
                        issues.append({
                            "type": "potential_duplicate",
                            "severity": "warning",
                            "message": f"Multiple W-2s from same employer (EIN: {ein})",
                            "documents": [seen_employers[ein], doc.document_id],
                        })
                    else:
                        seen_employers[ein] = doc.document_id

        # Check for SSN consistency across documents
        ssns = set()
        for doc in documents:
            ssn = doc.get_field_value("ssn") or doc.get_field_value("recipient_tin")
            if ssn:
                # Normalize SSN
                ssn_normalized = re.sub(r'[^0-9]', '', str(ssn))
                if len(ssn_normalized) == 9:
                    ssns.add(ssn_normalized)

        if len(ssns) > 1:
            issues.append({
                "type": "ssn_mismatch",
                "severity": "error",
                "message": "Documents contain different SSNs - may belong to different taxpayers",
                "details": f"Found {len(ssns)} different SSNs",
            })

        # Check withholding reasonableness
        total_wages = Decimal("0")
        total_withheld = Decimal("0")
        for doc in documents:
            if doc.document_type == DocumentType.W2:
                total_wages += Decimal(str(doc.get_field_value("wages", 0) or 0))
                total_withheld += Decimal(str(doc.get_field_value("federal_tax_withheld", 0) or 0))

        if total_wages > 0:
            withholding_rate = total_withheld / total_wages
            if withholding_rate > Decimal("0.40"):
                issues.append({
                    "type": "high_withholding",
                    "severity": "info",
                    "message": f"Federal withholding is {withholding_rate:.1%} of wages - higher than typical",
                    "details": "You may be over-withholding and could adjust your W-4",
                })
            elif withholding_rate < Decimal("0.05") and total_wages > 50000:
                issues.append({
                    "type": "low_withholding",
                    "severity": "warning",
                    "message": f"Federal withholding is only {withholding_rate:.1%} of wages",
                    "details": "You may owe taxes - consider adjusting your W-4",
                })

        return issues

    def _normalize_document_type(self, doc_type: str) -> DocumentType:
        """Normalize document type string to enum."""
        doc_type_lower = doc_type.lower().replace("-", "_").replace(" ", "_")

        type_mapping = {
            "w2": DocumentType.W2,
            "w_2": DocumentType.W2,
            "form_w2": DocumentType.W2,
            "1099_nec": DocumentType.FORM_1099_NEC,
            "1099nec": DocumentType.FORM_1099_NEC,
            "1099_int": DocumentType.FORM_1099_INT,
            "1099int": DocumentType.FORM_1099_INT,
            "1099_div": DocumentType.FORM_1099_DIV,
            "1099div": DocumentType.FORM_1099_DIV,
            "1099_b": DocumentType.FORM_1099_B,
            "1099b": DocumentType.FORM_1099_B,
            "1099_r": DocumentType.FORM_1099_R,
            "1099r": DocumentType.FORM_1099_R,
            "1099_g": DocumentType.FORM_1099_G,
            "1099g": DocumentType.FORM_1099_G,
            "1099_sa": DocumentType.FORM_1099_SA,
            "1098": DocumentType.FORM_1098,
            "1098_t": DocumentType.FORM_1098_T,
            "1098t": DocumentType.FORM_1098_T,
            "1098_e": DocumentType.FORM_1098_E,
            "k1": DocumentType.SCHEDULE_K1,
            "schedule_k1": DocumentType.SCHEDULE_K1,
        }

        return type_mapping.get(doc_type_lower, DocumentType.UNKNOWN)

    def _normalize_value(self, field_name: str, raw_value: Any) -> Any:
        """Normalize a field value based on field type."""
        if raw_value is None:
            return None

        field_type = self._get_field_type(field_name)

        if field_type == "currency":
            return self._parse_currency(raw_value)
        elif field_type == "ein":
            return self._normalize_ein(raw_value)
        elif field_type == "ssn":
            return self._normalize_ssn(raw_value)
        else:
            return raw_value

    def _parse_currency(self, value: Any) -> Decimal:
        """Parse currency value to Decimal."""
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))

        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$,\s]', '', value)
            try:
                return Decimal(cleaned)
            except (ValueError, TypeError, ArithmeticError):
                return Decimal("0")

        return Decimal("0")

    def _normalize_ein(self, value: Any) -> str:
        """Normalize EIN to XX-XXXXXXX format."""
        digits = re.sub(r'[^0-9]', '', str(value))
        if len(digits) == 9:
            return f"{digits[:2]}-{digits[2:]}"
        return str(value)

    def _normalize_ssn(self, value: Any) -> str:
        """Normalize SSN to XXX-XX-XXXX format."""
        digits = re.sub(r'[^0-9]', '', str(value))
        if len(digits) == 9:
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        return str(value)

    def _get_field_type(self, field_name: str) -> str:
        """Determine field type based on field name."""
        currency_fields = [
            "wages", "federal_tax_withheld", "state_tax_withheld", "local_tax_withheld",
            "social_security_wages", "social_security_tax", "medicare_wages", "medicare_tax",
            "interest_income", "ordinary_dividends", "qualified_dividends", "capital_gain_distributions",
            "nonemployee_compensation", "gross_distribution", "taxable_amount",
            "mortgage_interest", "points_paid", "amounts_billed", "scholarships",
            "proceeds", "cost_basis", "gain_loss",
        ]

        if field_name.lower() in currency_fields:
            return "currency"
        elif "ein" in field_name.lower() or "tin" in field_name.lower():
            return "ein"
        elif "ssn" in field_name.lower():
            return "ssn"
        else:
            return "string"

    def _check_review_needed(
        self,
        doc_type: DocumentType,
        fields: List[ExtractedField],
        inference_result: InferenceResult,
        overall_confidence: float,
    ) -> Tuple[bool, List[str]]:
        """Check if document needs manual review."""
        needs_review = False
        reasons = []

        # Low confidence
        if overall_confidence < 70:
            needs_review = True
            reasons.append(f"Low extraction confidence ({overall_confidence:.0f}%)")

        # Missing required fields
        required = self.REQUIRED_FIELDS.get(doc_type, [])
        field_names = {f.name for f in fields}
        missing = [r for r in required if r not in field_names]
        if missing:
            needs_review = True
            reasons.append(f"Missing required fields: {', '.join(missing)}")

        # Validation issues
        critical_issues = [
            issue for issue in inference_result.validation_issues
            if issue.severity == "error"
        ]
        if critical_issues:
            needs_review = True
            reasons.append(f"{len(critical_issues)} validation error(s) found")

        # Low confidence on key fields
        for field in fields:
            if field.name in required and field.confidence.overall_score < 60:
                needs_review = True
                reasons.append(f"Low confidence on {field.name} ({field.confidence.overall_score:.0f}%)")

        return needs_review, reasons
