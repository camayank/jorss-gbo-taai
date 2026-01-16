"""
Document Processor - Main orchestrator for document OCR and data extraction.

Handles:
- Document upload and storage
- Document type classification
- OCR processing
- Field extraction
- Data validation
- Integration with tax return models
"""

from __future__ import annotations

import os
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from .ocr_engine import OCREngine, OCRResult, OCREngineType
from .field_extractor import (
    FieldExtractor,
    ExtractedField,
    get_templates_for_document,
    FieldType,
)


@dataclass
class DocumentClassification:
    """Result of document type classification."""
    document_type: str
    confidence: float
    tax_year: int
    indicators: List[str] = field(default_factory=list)


@dataclass
class ProcessingResult:
    """Result of document processing."""
    document_id: UUID
    document_type: str
    tax_year: int
    status: str
    ocr_confidence: float
    extraction_confidence: float
    extracted_fields: List[ExtractedField]
    raw_text: str
    processing_time_ms: int
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "document_id": str(self.document_id),
            "document_type": self.document_type,
            "tax_year": self.tax_year,
            "status": self.status,
            "ocr_confidence": self.ocr_confidence,
            "extraction_confidence": self.extraction_confidence,
            "extracted_fields": [f.to_dict() for f in self.extracted_fields],
            "raw_text": self.raw_text,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def get_extracted_data(self) -> Dict[str, Any]:
        """Get extracted data as a flat dictionary (JSON serializable)."""
        from decimal import Decimal
        data = {}
        for field in self.extracted_fields:
            if field.normalized_value is not None:
                value = field.normalized_value
                # Convert Decimal to float for JSON serialization
                if isinstance(value, Decimal):
                    value = float(value)
                data[field.field_name] = value
        return data


class DocumentProcessor:
    """
    Main document processing orchestrator.

    Handles the complete workflow of processing tax documents:
    1. Accept uploaded document
    2. Classify document type
    3. Run OCR
    4. Extract fields
    5. Validate data
    6. Return structured results

    Usage:
        processor = DocumentProcessor()
        result = processor.process_document("/path/to/w2.pdf")
        if result.status == "success":
            w2_data = result.get_extracted_data()
    """

    # Document type indicators for classification
    DOCUMENT_INDICATORS = {
        "w2": [
            r"form\s*w-?2",
            r"wage\s+and\s+tax\s+statement",
            r"employer.s?\s+identification\s+number",
            r"box\s*1.*wages.*tips",
            r"social\s+security\s+wages",
            r"medicare\s+wages",
        ],
        "1099-int": [
            r"form\s*1099-?int",
            r"interest\s+income",
            r"early\s+withdrawal\s+penalty",
            r"tax.exempt\s+interest",
        ],
        "1099-div": [
            r"form\s*1099-?div",
            r"dividends\s+and\s+distributions",
            r"ordinary\s+dividends",
            r"qualified\s+dividends",
            r"capital\s+gain\s+(?:distr|dist)",
        ],
        "1099-nec": [
            r"form\s*1099-?nec",
            r"nonemployee\s+compensation",
        ],
        "1099-misc": [
            r"form\s*1099-?misc",
            r"miscellaneous\s+(?:income|information)",
            r"rents.*royalties",
        ],
        "1099-b": [
            r"form\s*1099-?b",
            r"proceeds\s+from\s+broker",
            r"barter\s+exchange",
            r"cost\s+or\s+other\s+basis",
        ],
        "1099-r": [
            r"form\s*1099-?r",
            r"distributions\s+from\s+pensions",
            r"annuities.*retirement",
            r"ira.*distribution",
        ],
        "1099-g": [
            r"form\s*1099-?g",
            r"government\s+payments",
            r"unemployment\s+compensation",
            r"state.*local\s+income\s+tax\s+refunds",
        ],
        "1098": [
            r"form\s*1098\b",
            r"mortgage\s+interest\s+statement",
            r"mortgage\s+interest\s+received",
        ],
        "1098-e": [
            r"form\s*1098-?e",
            r"student\s+loan\s+interest",
        ],
        "1098-t": [
            r"form\s*1098-?t",
            r"tuition\s+statement",
            r"payments\s+received.*qualified\s+tuition",
        ],
        "k1": [
            r"schedule\s*k-?1",
            r"partner.s?\s+share",
            r"shareholder.s?\s+share",
            r"beneficiary.s?\s+share",
        ],
    }

    # Tax year patterns
    TAX_YEAR_PATTERNS = [
        r"(?:tax\s+year|for\s+calendar\s+year)\s*:?\s*(\d{4})",
        r"(\d{4})\s+form\s+(?:w-?2|1099)",
        r"form\s+(?:w-?2|1099).*?(\d{4})",
        r"(?:copy\s+[abc12].*?)?(\d{4})",
    ]

    def __init__(
        self,
        ocr_engine: Optional[OCREngine] = None,
        storage_path: Optional[str] = None,
        default_tax_year: int = 2025,
    ):
        """
        Initialize document processor.

        Args:
            ocr_engine: OCR engine to use (defaults to Tesseract)
            storage_path: Path to store uploaded documents
            default_tax_year: Default tax year if not detected
        """
        self.ocr_engine = ocr_engine or OCREngine(engine_type=OCREngineType.TESSERACT)
        self.field_extractor = FieldExtractor()
        self.storage_path = storage_path or "/tmp/tax_documents"
        self.default_tax_year = default_tax_year

        # Ensure storage directory exists
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

    def process_document(
        self,
        file_path: str,
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> ProcessingResult:
        """
        Process a tax document from file.

        Args:
            file_path: Path to the document file
            document_type: Optional document type override
            tax_year: Optional tax year override

        Returns:
            ProcessingResult with extracted data
        """
        document_id = uuid4()
        warnings = []
        errors = []
        start_time = datetime.now()

        # Run OCR
        try:
            ocr_result = self.ocr_engine.process(file_path)
        except Exception as e:
            return ProcessingResult(
                document_id=document_id,
                document_type="unknown",
                tax_year=tax_year or self.default_tax_year,
                status="failed",
                ocr_confidence=0.0,
                extraction_confidence=0.0,
                extracted_fields=[],
                raw_text="",
                processing_time_ms=self._get_elapsed_ms(start_time),
                errors=[f"OCR failed: {str(e)}"],
            )

        if not ocr_result.raw_text:
            return ProcessingResult(
                document_id=document_id,
                document_type="unknown",
                tax_year=tax_year or self.default_tax_year,
                status="failed",
                ocr_confidence=0.0,
                extraction_confidence=0.0,
                extracted_fields=[],
                raw_text="",
                processing_time_ms=self._get_elapsed_ms(start_time),
                errors=["No text extracted from document"],
            )

        # Classify document
        if document_type:
            classification = DocumentClassification(
                document_type=document_type,
                confidence=100.0,
                tax_year=tax_year or self._detect_tax_year(ocr_result.raw_text),
                indicators=["User specified"],
            )
        else:
            classification = self._classify_document(ocr_result.raw_text)
            if classification.confidence < 50:
                warnings.append(f"Low document classification confidence: {classification.confidence:.1f}%")

        # Override tax year if specified
        if tax_year:
            classification.tax_year = tax_year

        # Get templates for document type
        templates = get_templates_for_document(classification.document_type)
        if not templates:
            warnings.append(f"No extraction templates for document type: {classification.document_type}")

        # Extract fields
        extracted_fields = self.field_extractor.extract(ocr_result, templates)

        # Calculate extraction confidence
        extraction_confidence = self._calculate_extraction_confidence(extracted_fields, templates)

        # Validate extracted data
        validation_warnings = self._validate_extracted_data(classification.document_type, extracted_fields)
        warnings.extend(validation_warnings)

        # Determine status
        if errors:
            status = "failed"
        elif extraction_confidence < 50:
            status = "needs_review"
        elif warnings:
            status = "completed_with_warnings"
        else:
            status = "success"

        return ProcessingResult(
            document_id=document_id,
            document_type=classification.document_type,
            tax_year=classification.tax_year,
            status=status,
            ocr_confidence=ocr_result.confidence,
            extraction_confidence=extraction_confidence,
            extracted_fields=extracted_fields,
            raw_text=ocr_result.raw_text,
            processing_time_ms=self._get_elapsed_ms(start_time),
            warnings=warnings,
            errors=errors,
        )

    def process_bytes(
        self,
        data: bytes,
        mime_type: str,
        original_filename: str,
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> ProcessingResult:
        """
        Process a tax document from bytes.

        Args:
            data: Document bytes
            mime_type: MIME type of the document
            original_filename: Original filename for reference
            document_type: Optional document type override
            tax_year: Optional tax year override

        Returns:
            ProcessingResult with extracted data
        """
        document_id = uuid4()
        warnings = []
        errors = []
        start_time = datetime.now()

        # Run OCR
        try:
            ocr_result = self.ocr_engine.process_bytes(data, mime_type)
        except Exception as e:
            return ProcessingResult(
                document_id=document_id,
                document_type="unknown",
                tax_year=tax_year or self.default_tax_year,
                status="failed",
                ocr_confidence=0.0,
                extraction_confidence=0.0,
                extracted_fields=[],
                raw_text="",
                processing_time_ms=self._get_elapsed_ms(start_time),
                errors=[f"OCR failed: {str(e)}"],
            )

        if not ocr_result.raw_text:
            return ProcessingResult(
                document_id=document_id,
                document_type="unknown",
                tax_year=tax_year or self.default_tax_year,
                status="failed",
                ocr_confidence=0.0,
                extraction_confidence=0.0,
                extracted_fields=[],
                raw_text="",
                processing_time_ms=self._get_elapsed_ms(start_time),
                errors=["No text extracted from document"],
            )

        # Classify and extract (same as process_document)
        if document_type:
            classification = DocumentClassification(
                document_type=document_type,
                confidence=100.0,
                tax_year=tax_year or self._detect_tax_year(ocr_result.raw_text),
                indicators=["User specified"],
            )
        else:
            classification = self._classify_document(ocr_result.raw_text)
            if classification.confidence < 50:
                warnings.append(f"Low document classification confidence: {classification.confidence:.1f}%")

        if tax_year:
            classification.tax_year = tax_year

        templates = get_templates_for_document(classification.document_type)
        if not templates:
            warnings.append(f"No extraction templates for document type: {classification.document_type}")

        extracted_fields = self.field_extractor.extract(ocr_result, templates)
        extraction_confidence = self._calculate_extraction_confidence(extracted_fields, templates)
        validation_warnings = self._validate_extracted_data(classification.document_type, extracted_fields)
        warnings.extend(validation_warnings)

        if errors:
            status = "failed"
        elif extraction_confidence < 50:
            status = "needs_review"
        elif warnings:
            status = "completed_with_warnings"
        else:
            status = "success"

        return ProcessingResult(
            document_id=document_id,
            document_type=classification.document_type,
            tax_year=classification.tax_year,
            status=status,
            ocr_confidence=ocr_result.confidence,
            extraction_confidence=extraction_confidence,
            extracted_fields=extracted_fields,
            raw_text=ocr_result.raw_text,
            processing_time_ms=self._get_elapsed_ms(start_time),
            warnings=warnings,
            errors=errors,
        )

    def _classify_document(self, text: str) -> DocumentClassification:
        """Classify document type based on text content."""
        text_lower = text.lower()
        scores = {}

        for doc_type, patterns in self.DOCUMENT_INDICATORS.items():
            score = 0
            matched_indicators = []

            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
                    matched_indicators.append(pattern)

            if score > 0:
                # Normalize score (percentage of patterns matched)
                scores[doc_type] = {
                    "score": score / len(patterns) * 100,
                    "indicators": matched_indicators,
                }

        if not scores:
            return DocumentClassification(
                document_type="unknown",
                confidence=0.0,
                tax_year=self._detect_tax_year(text),
                indicators=[],
            )

        # Get highest scoring document type
        best_type = max(scores.keys(), key=lambda k: scores[k]["score"])
        best_score = scores[best_type]

        return DocumentClassification(
            document_type=best_type,
            confidence=best_score["score"],
            tax_year=self._detect_tax_year(text),
            indicators=best_score["indicators"],
        )

    def _detect_tax_year(self, text: str) -> int:
        """Detect tax year from document text."""
        for pattern in self.TAX_YEAR_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                # Validate reasonable tax year range
                if 2000 <= year <= 2030:
                    return year

        return self.default_tax_year

    def _calculate_extraction_confidence(
        self,
        fields: List[ExtractedField],
        templates
    ) -> float:
        """Calculate overall extraction confidence."""
        if not fields:
            return 0.0

        total_confidence = 0.0
        required_found = 0
        required_total = 0

        for template in templates:
            if template.required:
                required_total += 1

        for field in fields:
            total_confidence += field.confidence

            # Check if required field
            for template in templates:
                if template.field_name == field.field_name and template.required:
                    if field.normalized_value is not None:
                        required_found += 1
                    break

        # Base confidence on field extraction
        base_confidence = total_confidence / len(fields) if fields else 0

        # Penalty for missing required fields
        if required_total > 0:
            required_penalty = (required_total - required_found) / required_total * 30
            base_confidence = max(0, base_confidence - required_penalty)

        return min(100.0, base_confidence)

    def _validate_extracted_data(
        self,
        document_type: str,
        fields: List[ExtractedField]
    ) -> List[str]:
        """Validate extracted data for consistency."""
        warnings = []

        if document_type == "w2":
            warnings.extend(self._validate_w2_data(fields))
        elif document_type.startswith("1099"):
            warnings.extend(self._validate_1099_data(fields))

        return warnings

    def _validate_w2_data(self, fields: List[ExtractedField]) -> List[str]:
        """Validate W-2 specific data."""
        warnings = []
        field_dict = {f.field_name: f.normalized_value for f in fields}

        # Check wages vs social security wages
        wages = field_dict.get("wages")
        ss_wages = field_dict.get("social_security_wages")

        if wages and ss_wages:
            # SS wage base limit for 2025 is $176,100
            ss_wage_limit = 176100
            if ss_wages > ss_wage_limit:
                warnings.append(f"Social security wages (${ss_wages:,.2f}) exceed 2025 limit (${ss_wage_limit:,})")

        # Check federal withholding is reasonable
        fed_withheld = field_dict.get("federal_tax_withheld")
        if wages and fed_withheld:
            withholding_rate = fed_withheld / wages if wages > 0 else 0
            if withholding_rate > 0.50:
                warnings.append(f"Federal withholding rate ({withholding_rate:.1%}) seems unusually high")
            elif withholding_rate < 0.0:
                warnings.append("Federal withholding appears negative")

        return warnings

    def _validate_1099_data(self, fields: List[ExtractedField]) -> List[str]:
        """Validate 1099 specific data."""
        warnings = []
        field_dict = {f.field_name: f.normalized_value for f in fields}

        # Check for negative amounts
        for field in fields:
            if field.field_type in [FieldType.CURRENCY, FieldType.DECIMAL]:
                if field.normalized_value is not None and field.normalized_value < 0:
                    warnings.append(f"{field.field_label} appears negative: ${field.normalized_value:,.2f}")

        return warnings

    def _get_elapsed_ms(self, start_time: datetime) -> int:
        """Get elapsed time in milliseconds."""
        return int((datetime.now() - start_time).total_seconds() * 1000)

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Compute SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    @staticmethod
    def compute_bytes_hash(data: bytes) -> str:
        """Compute SHA256 hash of bytes."""
        return hashlib.sha256(data).hexdigest()

    def get_supported_document_types(self) -> List[str]:
        """Get list of supported document types."""
        return list(self.DOCUMENT_INDICATORS.keys())


class DocumentIntegration:
    """
    Integrates extracted document data with tax return models.

    Handles mapping extracted fields to the appropriate
    tax return model fields and creating/updating records.
    """

    def __init__(self):
        pass

    def apply_w2_to_return(
        self,
        result: ProcessingResult,
        tax_return: Any
    ) -> Tuple[bool, List[str]]:
        """
        Apply extracted W-2 data to a tax return.

        Args:
            result: ProcessingResult from document processing
            tax_return: TaxReturn model instance

        Returns:
            Tuple of (success, list of warnings/errors)
        """
        if result.document_type != "w2":
            return False, ["Document is not a W-2"]

        errors = []
        data = result.get_extracted_data()

        try:
            # Import here to avoid circular imports
            from models.income import W2Info

            w2 = W2Info(
                employer_name=data.get("employer_name", "Unknown Employer"),
                employer_ein=data.get("employer_ein", ""),
                wages=float(data.get("wages", 0)),
                federal_tax_withheld=float(data.get("federal_tax_withheld", 0)),
                social_security_wages=float(data.get("social_security_wages", 0)),
                social_security_tax=float(data.get("social_security_tax", 0)),
                medicare_wages=float(data.get("medicare_wages", 0)),
                medicare_tax=float(data.get("medicare_tax", 0)),
                state=data.get("state", ""),
                state_wages=float(data.get("state_wages", 0)),
                state_tax=float(data.get("state_tax", 0)),
            )

            # Add W-2 to tax return
            tax_return.income.w2_forms.append(w2)
            return True, []

        except Exception as e:
            return False, [f"Failed to apply W-2: {str(e)}"]

    def apply_1099_int_to_return(
        self,
        result: ProcessingResult,
        tax_return: Any
    ) -> Tuple[bool, List[str]]:
        """Apply extracted 1099-INT data to a tax return."""
        if result.document_type != "1099-int":
            return False, ["Document is not a 1099-INT"]

        data = result.get_extracted_data()

        try:
            # Add interest income to tax return
            interest = float(data.get("interest_income", 0))
            tax_return.income.interest_income += interest

            # Track tax-exempt interest separately
            tax_exempt = float(data.get("tax_exempt_interest", 0))
            if hasattr(tax_return.income, 'tax_exempt_interest'):
                tax_return.income.tax_exempt_interest += tax_exempt

            return True, []

        except Exception as e:
            return False, [f"Failed to apply 1099-INT: {str(e)}"]

    def apply_1099_div_to_return(
        self,
        result: ProcessingResult,
        tax_return: Any
    ) -> Tuple[bool, List[str]]:
        """Apply extracted 1099-DIV data to a tax return."""
        if result.document_type != "1099-div":
            return False, ["Document is not a 1099-DIV"]

        data = result.get_extracted_data()

        try:
            # Add dividend income
            ordinary = float(data.get("ordinary_dividends", 0))
            qualified = float(data.get("qualified_dividends", 0))

            tax_return.income.ordinary_dividends += ordinary
            tax_return.income.qualified_dividends += qualified

            # Capital gain distributions go to capital gains
            cap_gains = float(data.get("capital_gain_distributions", 0))
            if cap_gains > 0:
                tax_return.income.long_term_capital_gains += cap_gains

            return True, []

        except Exception as e:
            return False, [f"Failed to apply 1099-DIV: {str(e)}"]

    def apply_1099_nec_to_return(
        self,
        result: ProcessingResult,
        tax_return: Any
    ) -> Tuple[bool, List[str]]:
        """Apply extracted 1099-NEC data to a tax return."""
        if result.document_type != "1099-nec":
            return False, ["Document is not a 1099-NEC"]

        data = result.get_extracted_data()

        try:
            # Add self-employment income
            compensation = float(data.get("nonemployee_compensation", 0))
            tax_return.income.self_employment_income += compensation

            return True, []

        except Exception as e:
            return False, [f"Failed to apply 1099-NEC: {str(e)}"]

    def apply_document_to_return(
        self,
        result: ProcessingResult,
        tax_return: Any
    ) -> Tuple[bool, List[str]]:
        """
        Apply any supported document to a tax return.

        Routes to the appropriate handler based on document type.
        """
        handlers = {
            "w2": self.apply_w2_to_return,
            "1099-int": self.apply_1099_int_to_return,
            "1099-div": self.apply_1099_div_to_return,
            "1099-nec": self.apply_1099_nec_to_return,
        }

        handler = handlers.get(result.document_type)
        if handler:
            return handler(result, tax_return)
        else:
            return False, [f"No handler for document type: {result.document_type}"]
