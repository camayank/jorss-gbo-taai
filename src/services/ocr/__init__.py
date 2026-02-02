"""
OCR Service Module - Document processing and data extraction.

This module provides:
- Multi-engine OCR support (Tesseract, AWS Textract, Google Vision)
- Document type classification
- Field extraction for tax forms (W-2, 1099, 1098, etc.)
- Data validation and normalization
- Resilient processing with retry and circuit breaker patterns
- Multi-factor confidence scoring
- Intelligent field inference
"""

from .document_processor import DocumentProcessor, ProcessingResult, DocumentIntegration
from .ocr_engine import OCREngine, OCRResult, OCREngineError, OCREngineType
from .field_extractor import FieldExtractor, ExtractedField
from .resilient_processor import (
    ResilientOCREngine,
    ResilientDocumentProcessor,
    ResilientOCRConfig,
    get_circuit_breaker_stats,
    reset_all_circuit_breakers,
)
from .confidence_scorer import (
    ConfidenceScorer,
    ConfidenceResult,
    ConfidenceLevel,
    ConfidenceFactors,
    DocumentConfidenceAggregator,
    calculate_field_confidence,
    get_confidence_band,
)
from .inference_engine import (
    FieldInferenceEngine,
    InferenceResult,
    InferredField,
    InferenceType,
    ValidationIssue,
    MultiDocumentInference,
    infer_document_fields,
    aggregate_multi_document_income,
)
from .ai_enhanced_processor import (
    AIEnhancedDocumentProcessor,
    AIEnhancedResult,
    get_ai_enhanced_processor,
)

__all__ = [
    # Core processors
    "DocumentProcessor",
    "ProcessingResult",
    "DocumentIntegration",
    "OCREngine",
    "OCRResult",
    "OCREngineError",
    "OCREngineType",
    "FieldExtractor",
    "ExtractedField",
    # Resilient processors
    "ResilientOCREngine",
    "ResilientDocumentProcessor",
    "ResilientOCRConfig",
    "get_circuit_breaker_stats",
    "reset_all_circuit_breakers",
    # Confidence scoring
    "ConfidenceScorer",
    "ConfidenceResult",
    "ConfidenceLevel",
    "ConfidenceFactors",
    "DocumentConfidenceAggregator",
    "calculate_field_confidence",
    "get_confidence_band",
    # Inference engine
    "FieldInferenceEngine",
    "InferenceResult",
    "InferredField",
    "InferenceType",
    "ValidationIssue",
    "MultiDocumentInference",
    "infer_document_fields",
    "aggregate_multi_document_income",
    # AI-enhanced processing
    "AIEnhancedDocumentProcessor",
    "AIEnhancedResult",
    "get_ai_enhanced_processor",
]
