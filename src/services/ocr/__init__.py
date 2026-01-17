"""
OCR Service Module - Document processing and data extraction.

This module provides:
- Multi-engine OCR support (Tesseract, AWS Textract, Google Vision)
- Document type classification
- Field extraction for tax forms (W-2, 1099, 1098, etc.)
- Data validation and normalization
- Resilient processing with retry and circuit breaker patterns
"""

from .document_processor import DocumentProcessor, ProcessingResult, DocumentIntegration
from .ocr_engine import OCREngine, OCRResult
from .field_extractor import FieldExtractor, ExtractedField
from .resilient_processor import (
    ResilientOCREngine,
    ResilientDocumentProcessor,
    ResilientOCRConfig,
    get_circuit_breaker_stats,
    reset_all_circuit_breakers,
)

__all__ = [
    # Core processors
    "DocumentProcessor",
    "ProcessingResult",
    "DocumentIntegration",
    "OCREngine",
    "OCRResult",
    "FieldExtractor",
    "ExtractedField",
    # Resilient processors
    "ResilientOCREngine",
    "ResilientDocumentProcessor",
    "ResilientOCRConfig",
    "get_circuit_breaker_stats",
    "reset_all_circuit_breakers",
]
