"""
AI-Enhanced Document Processor.

Integrates AI-powered document intelligence with the traditional OCR pipeline:
- Gemini multimodal for document classification and extraction
- AI fallback when OCR confidence is low
- Anomaly detection on extracted tax data
- Compliance review integration

Usage:
    from services.ocr.ai_enhanced_processor import AIEnhancedDocumentProcessor

    processor = AIEnhancedDocumentProcessor()

    # Process with AI enhancement
    result = await processor.process_with_ai(image_bytes, "image/jpeg")

    # Run anomaly detection on extracted data
    anomalies = await processor.detect_anomalies(result)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from .document_processor import (
    DocumentProcessor,
    ProcessingResult,
    DocumentClassification,
)
from .field_extractor import ExtractedField as OCRExtractedField

logger = logging.getLogger(__name__)


@dataclass
class AIEnhancedResult:
    """Result from AI-enhanced document processing."""

    # Core processing result
    document_id: UUID
    document_type: str
    tax_year: int
    status: str

    # OCR results
    ocr_confidence: float
    ocr_fields: List[OCRExtractedField]

    # AI enhancement results
    ai_used: bool
    ai_confidence: float
    ai_fields: Dict[str, Any]
    ai_classification_used: bool

    # Combined results
    final_confidence: float
    extracted_fields: List[OCRExtractedField]
    raw_text: str

    # Anomaly detection
    anomalies_checked: bool
    anomaly_count: int
    high_severity_anomalies: int
    audit_risk_score: Optional[float]

    # Compliance
    compliance_checked: bool
    compliance_issues: int

    # Metadata
    processing_time_ms: int
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "document_id": str(self.document_id),
            "document_type": self.document_type,
            "tax_year": self.tax_year,
            "status": self.status,
            "ocr_confidence": self.ocr_confidence,
            "ai_used": self.ai_used,
            "ai_confidence": self.ai_confidence,
            "ai_classification_used": self.ai_classification_used,
            "final_confidence": self.final_confidence,
            "extracted_fields": [f.to_dict() for f in self.extracted_fields],
            "raw_text": self.raw_text,
            "anomalies_checked": self.anomalies_checked,
            "anomaly_count": self.anomaly_count,
            "high_severity_anomalies": self.high_severity_anomalies,
            "audit_risk_score": self.audit_risk_score,
            "compliance_checked": self.compliance_checked,
            "compliance_issues": self.compliance_issues,
            "processing_time_ms": self.processing_time_ms,
            "warnings": self.warnings,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat(),
        }


class AIEnhancedDocumentProcessor:
    """
    AI-enhanced document processor combining OCR with AI intelligence.

    Processing Pipeline:
    1. Traditional OCR extraction (fast, cost-effective)
    2. AI classification when OCR confidence < threshold
    3. AI extraction as fallback for low-confidence fields
    4. Anomaly detection on extracted data
    5. Compliance review for tax returns

    Features:
    - Hybrid OCR + AI approach for optimal accuracy/cost balance
    - Automatic AI fallback when OCR struggles
    - Integrated anomaly and compliance checking
    - Detailed confidence scoring at each stage
    """

    # Confidence thresholds
    OCR_CONFIDENCE_THRESHOLD = 70.0  # Below this, try AI
    AI_CONFIDENCE_THRESHOLD = 80.0   # AI needs this confidence to override
    FIELD_CONFIDENCE_THRESHOLD = 60.0  # Per-field threshold for AI enhancement

    def __init__(
        self,
        ocr_processor: Optional[DocumentProcessor] = None,
        enable_ai_fallback: bool = True,
        enable_anomaly_detection: bool = True,
        enable_compliance_check: bool = False,  # Off by default (expensive)
    ):
        """
        Initialize AI-enhanced processor.

        Args:
            ocr_processor: Traditional OCR processor (creates default if None)
            enable_ai_fallback: Whether to use AI when OCR confidence is low
            enable_anomaly_detection: Whether to run anomaly detection
            enable_compliance_check: Whether to run compliance review
        """
        self.ocr_processor = ocr_processor or DocumentProcessor()
        self.enable_ai_fallback = enable_ai_fallback
        self.enable_anomaly_detection = enable_anomaly_detection
        self.enable_compliance_check = enable_compliance_check

        # Lazy-load AI services
        self._ai_processor = None
        self._anomaly_detector = None
        self._compliance_reviewer = None

    @property
    def ai_processor(self):
        """Lazy-load AI document processor."""
        if self._ai_processor is None:
            from services.ai.document_processor import get_document_processor
            self._ai_processor = get_document_processor()
        return self._ai_processor

    @property
    def anomaly_detector(self):
        """Lazy-load anomaly detector."""
        if self._anomaly_detector is None:
            from services.ai.anomaly_detector import get_anomaly_detector
            self._anomaly_detector = get_anomaly_detector()
        return self._anomaly_detector

    @property
    def compliance_reviewer(self):
        """Lazy-load compliance reviewer."""
        if self._compliance_reviewer is None:
            from services.ai.compliance_reviewer import get_compliance_reviewer
            self._compliance_reviewer = get_compliance_reviewer()
        return self._compliance_reviewer

    async def process_with_ai(
        self,
        data: bytes,
        mime_type: str,
        original_filename: str = "document",
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
        force_ai: bool = False,
    ) -> AIEnhancedResult:
        """
        Process document with AI enhancement.

        Args:
            data: Document bytes
            mime_type: MIME type of document
            original_filename: Original filename
            document_type: Optional document type override
            tax_year: Optional tax year override
            force_ai: Force AI processing regardless of OCR confidence

        Returns:
            AIEnhancedResult with combined OCR and AI results
        """
        document_id = uuid4()
        start_time = datetime.now()
        warnings = []
        errors = []

        ai_used = False
        ai_confidence = 0.0
        ai_fields = {}
        ai_classification_used = False
        anomalies_checked = False
        anomaly_count = 0
        high_severity_anomalies = 0
        audit_risk_score = None
        compliance_checked = False
        compliance_issues = 0

        # Step 1: Traditional OCR processing
        ocr_result = self.ocr_processor.process_bytes(
            data=data,
            mime_type=mime_type,
            original_filename=original_filename,
            document_type=document_type,
            tax_year=tax_year,
        )

        final_fields = list(ocr_result.extracted_fields)
        final_confidence = ocr_result.extraction_confidence
        final_type = ocr_result.document_type
        final_year = ocr_result.tax_year

        # Step 2: AI enhancement if needed
        needs_ai = (
            force_ai or
            (self.enable_ai_fallback and ocr_result.extraction_confidence < self.OCR_CONFIDENCE_THRESHOLD)
        )

        if needs_ai:
            try:
                ai_result = await self._run_ai_processing(data, document_type)
                ai_used = True
                ai_confidence = ai_result.classification_confidence

                # Use AI classification if more confident
                if (
                    ai_result.classification_confidence > self.AI_CONFIDENCE_THRESHOLD and
                    ai_result.classification_confidence > ocr_result.extraction_confidence
                ):
                    final_type = ai_result.document_type.value
                    ai_classification_used = True
                    if ai_result.tax_year:
                        final_year = ai_result.tax_year

                # Convert AI fields to match OCR format
                ai_fields = self._convert_ai_fields(ai_result)

                # Merge AI fields with low-confidence OCR fields
                final_fields = self._merge_fields(
                    ocr_fields=ocr_result.extracted_fields,
                    ai_fields=ai_fields,
                    threshold=self.FIELD_CONFIDENCE_THRESHOLD,
                )

                # Recalculate confidence
                final_confidence = self._calculate_merged_confidence(
                    ocr_result.extraction_confidence,
                    ai_result.classification_confidence,
                    ai_classification_used,
                )

                warnings.extend(ai_result.warnings)

            except Exception as e:
                logger.error(f"AI processing failed: {e}")
                errors.append(f"AI enhancement failed: {str(e)}")

        # Step 3: Anomaly detection
        if self.enable_anomaly_detection and final_fields:
            try:
                return_data = self._fields_to_return_data(final_fields, final_type, final_year)
                anomaly_report = await self.anomaly_detector.analyze_return(return_data)

                anomalies_checked = True
                anomaly_count = len(anomaly_report.anomalies)
                high_severity_anomalies = sum(
                    1 for a in anomaly_report.anomalies
                    if a.severity.value in ["high", "critical"]
                )

                # Add anomaly warnings
                for anomaly in anomaly_report.anomalies:
                    if anomaly.severity.value in ["high", "critical"]:
                        warnings.append(f"[{anomaly.severity.value.upper()}] {anomaly.description}")

            except Exception as e:
                logger.error(f"Anomaly detection failed: {e}")
                errors.append(f"Anomaly detection failed: {str(e)}")

        # Step 4: Audit risk assessment
        if anomalies_checked:
            try:
                return_data = self._fields_to_return_data(final_fields, final_type, final_year)
                risk_assessment = await self.anomaly_detector.assess_audit_risk(return_data)
                audit_risk_score = risk_assessment.overall_score

                if audit_risk_score > 70:
                    warnings.append(f"High audit risk score: {audit_risk_score:.1f}")

            except Exception as e:
                logger.error(f"Risk assessment failed: {e}")

        # Step 5: Compliance review (if enabled)
        if self.enable_compliance_check and final_fields:
            try:
                return_data = self._fields_to_return_data(final_fields, final_type, final_year)
                compliance_report = await self.compliance_reviewer.review_return(return_data)

                compliance_checked = True
                compliance_issues = len(compliance_report.issues)

                # Add compliance warnings
                for issue in compliance_report.issues:
                    if issue.status.value in ["non_compliant", "needs_documentation"]:
                        warnings.append(f"[COMPLIANCE] {issue.description}")

            except Exception as e:
                logger.error(f"Compliance review failed: {e}")
                errors.append(f"Compliance review failed: {str(e)}")

        # Determine final status
        if errors:
            status = "failed"
        elif high_severity_anomalies > 0:
            status = "needs_review"
        elif final_confidence < 50:
            status = "needs_review"
        elif warnings:
            status = "completed_with_warnings"
        else:
            status = "success"

        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

        return AIEnhancedResult(
            document_id=document_id,
            document_type=final_type,
            tax_year=final_year,
            status=status,
            ocr_confidence=ocr_result.extraction_confidence,
            ocr_fields=ocr_result.extracted_fields,
            ai_used=ai_used,
            ai_confidence=ai_confidence,
            ai_fields=ai_fields,
            ai_classification_used=ai_classification_used,
            final_confidence=final_confidence,
            extracted_fields=final_fields,
            raw_text=ocr_result.raw_text,
            anomalies_checked=anomalies_checked,
            anomaly_count=anomaly_count,
            high_severity_anomalies=high_severity_anomalies,
            audit_risk_score=audit_risk_score,
            compliance_checked=compliance_checked,
            compliance_issues=compliance_issues,
            processing_time_ms=processing_time,
            warnings=warnings,
            errors=errors,
        )

    async def _run_ai_processing(
        self,
        image_data: bytes,
        document_type: Optional[str] = None,
    ):
        """Run AI document processing."""
        from services.ai.document_processor import DocumentType

        # Convert string to DocumentType enum if provided
        doc_type = None
        if document_type:
            doc_type = self._string_to_document_type(document_type)

        return await self.ai_processor.process_document(
            image_data=image_data,
            document_type=doc_type,
        )

    def _string_to_document_type(self, type_str: str):
        """Convert string to DocumentType enum."""
        from services.ai.document_processor import DocumentType

        mapping = {
            "w2": DocumentType.W2,
            "1099-int": DocumentType.FORM_1099_INT,
            "1099-div": DocumentType.FORM_1099_DIV,
            "1099-b": DocumentType.FORM_1099_B,
            "1099-r": DocumentType.FORM_1099_R,
            "1099-misc": DocumentType.FORM_1099_MISC,
            "1099-nec": DocumentType.FORM_1099_NEC,
            "1099-g": DocumentType.FORM_1099_G,
            "1099-k": DocumentType.FORM_1099_K,
            "1098": DocumentType.FORM_1098,
            "1098-e": DocumentType.FORM_1098_E,
            "1098-t": DocumentType.FORM_1098_T,
            "k1": DocumentType.SCHEDULE_K1,
        }
        return mapping.get(type_str.lower())

    def _convert_ai_fields(self, ai_result) -> Dict[str, Any]:
        """Convert AI extraction result to dictionary."""
        fields = {}

        for field in ai_result.fields:
            field_name = field.box_label or field.name
            fields[field_name] = {
                "value": field.value,
                "confidence": field.confidence,
                "needs_review": field.needs_review,
            }

        # Add totals
        fields.update(ai_result.totals)

        return fields

    def _merge_fields(
        self,
        ocr_fields: List[OCRExtractedField],
        ai_fields: Dict[str, Any],
        threshold: float,
    ) -> List[OCRExtractedField]:
        """
        Merge OCR and AI fields, using AI for low-confidence OCR fields.

        Strategy:
        - Keep OCR field if confidence >= threshold
        - Replace with AI field if OCR confidence < threshold and AI has it
        - Add AI-only fields that OCR missed
        """
        merged = []
        used_ai_fields = set()

        for ocr_field in ocr_fields:
            if ocr_field.confidence >= threshold:
                merged.append(ocr_field)
            else:
                # Try to find AI equivalent
                ai_data = ai_fields.get(ocr_field.field_name)
                if ai_data and isinstance(ai_data, dict):
                    # Use AI value if more confident
                    if ai_data.get("confidence", 0) * 100 > ocr_field.confidence:
                        # Create updated field with AI value
                        updated = OCRExtractedField(
                            field_name=ocr_field.field_name,
                            field_label=ocr_field.field_label,
                            field_type=ocr_field.field_type,
                            raw_value=str(ai_data.get("value", "")),
                            normalized_value=ai_data.get("value"),
                            confidence=ai_data.get("confidence", 0) * 100,
                            extraction_method="ai_enhanced",
                        )
                        merged.append(updated)
                        used_ai_fields.add(ocr_field.field_name)
                    else:
                        merged.append(ocr_field)
                else:
                    merged.append(ocr_field)

        return merged

    def _calculate_merged_confidence(
        self,
        ocr_confidence: float,
        ai_confidence: float,
        ai_classification_used: bool,
    ) -> float:
        """Calculate combined confidence score."""
        if ai_classification_used:
            # Weight AI more heavily if we used its classification
            return (ocr_confidence * 0.4 + ai_confidence * 0.6)
        else:
            # OCR-primary with AI boost
            return (ocr_confidence * 0.7 + ai_confidence * 0.3)

    def _fields_to_return_data(
        self,
        fields: List[OCRExtractedField],
        document_type: str,
        tax_year: int,
    ) -> Dict[str, Any]:
        """Convert extracted fields to tax return data format."""
        data = {
            "tax_year": tax_year,
            "document_type": document_type,
            "filing_status": "single",  # Default
        }

        field_dict = {f.field_name: f.normalized_value for f in fields}

        # Map common fields
        if document_type == "w2":
            data["total_income"] = field_dict.get("wages", 0) or 0
            data["w2_wages"] = field_dict.get("wages", 0) or 0
            data["federal_withholding"] = field_dict.get("federal_tax_withheld", 0) or 0
        elif "1099" in document_type:
            data["total_income"] = sum(
                v for k, v in field_dict.items()
                if isinstance(v, (int, float)) and "income" in k.lower()
            )

        return data

    async def detect_anomalies(
        self,
        result: AIEnhancedResult,
        prior_year_data: Optional[Dict] = None,
    ):
        """
        Run anomaly detection on processing result.

        Args:
            result: AIEnhancedResult from processing
            prior_year_data: Optional prior year data for comparison

        Returns:
            AnomalyReport with detected anomalies
        """
        return_data = self._fields_to_return_data(
            result.extracted_fields,
            result.document_type,
            result.tax_year,
        )

        return await self.anomaly_detector.analyze_return(
            return_data,
            prior_year_data,
        )

    async def check_compliance(
        self,
        result: AIEnhancedResult,
        preparer_info: Optional[Dict] = None,
    ):
        """
        Run compliance review on processing result.

        Args:
            result: AIEnhancedResult from processing
            preparer_info: Optional preparer information

        Returns:
            ComplianceReport with compliance issues
        """
        return_data = self._fields_to_return_data(
            result.extracted_fields,
            result.document_type,
            result.tax_year,
        )

        return await self.compliance_reviewer.review_return(
            return_data,
            preparer_info,
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_ai_enhanced_processor: Optional[AIEnhancedDocumentProcessor] = None


def get_ai_enhanced_processor(
    enable_ai_fallback: bool = True,
    enable_anomaly_detection: bool = True,
    enable_compliance_check: bool = False,
) -> AIEnhancedDocumentProcessor:
    """Get the singleton AI-enhanced processor instance."""
    global _ai_enhanced_processor
    if _ai_enhanced_processor is None:
        _ai_enhanced_processor = AIEnhancedDocumentProcessor(
            enable_ai_fallback=enable_ai_fallback,
            enable_anomaly_detection=enable_anomaly_detection,
            enable_compliance_check=enable_compliance_check,
        )
    return _ai_enhanced_processor


__all__ = [
    "AIEnhancedDocumentProcessor",
    "AIEnhancedResult",
    "get_ai_enhanced_processor",
]
