"""
OCR Service Module - Document processing and data extraction.

This module provides:
- Multi-engine OCR support (Tesseract, AWS Textract, Google Vision)
- Document type classification
- Field extraction for tax forms (W-2, 1099, 1098, etc.)
- Data validation and normalization
"""

from .document_processor import DocumentProcessor, ProcessingResult, DocumentIntegration
from .ocr_engine import OCREngine, OCRResult
from .field_extractor import FieldExtractor, ExtractedField

__all__ = [
    "DocumentProcessor",
    "ProcessingResult",
    "DocumentIntegration",
    "OCREngine",
    "OCRResult",
    "FieldExtractor",
    "ExtractedField",
]
