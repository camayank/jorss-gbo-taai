"""
Services Module - Business logic services for the Tax Return Preparation Agent.

Includes:
- OCR document processing and data extraction
- Document validation and verification
- Integration with external services
"""

from .ocr import DocumentProcessor, OCREngine, FieldExtractor

__all__ = [
    "DocumentProcessor",
    "OCREngine",
    "FieldExtractor",
]
