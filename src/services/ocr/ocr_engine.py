"""
OCR Engine - Multi-backend OCR processing abstraction.

Supports:
- Tesseract (local, open-source)
- AWS Textract (cloud, high accuracy)
- Google Cloud Vision (cloud, alternative)
"""

from __future__ import annotations

import os
import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from pathlib import Path


class OCREngineType(str, Enum):
    """Supported OCR engines."""
    TESSERACT = "tesseract"
    AWS_TEXTRACT = "aws_textract"
    GOOGLE_VISION = "google_vision"
    MOCK = "mock"  # For testing


@dataclass
class BoundingBox:
    """Bounding box for detected text."""
    left: int
    top: int
    width: int
    height: int
    page: int = 1

    def to_dict(self) -> Dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "page": self.page,
        }


@dataclass
class TextBlock:
    """A block of text detected by OCR."""
    text: str
    confidence: float
    bbox: Optional[BoundingBox] = None
    block_type: str = "word"  # word, line, paragraph


@dataclass
class OCRResult:
    """Result from OCR processing."""
    raw_text: str
    blocks: List[TextBlock]
    confidence: float
    engine_used: str
    page_count: int = 1
    processing_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_text_by_region(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        page: int = 1
    ) -> Optional[str]:
        """Get text within a specific region."""
        matching_blocks = []
        for block in self.blocks:
            if block.bbox and block.bbox.page == page:
                # Check if block overlaps with region
                b = block.bbox
                if (b.left >= left and b.left + b.width <= left + width and
                    b.top >= top and b.top + b.height <= top + height):
                    matching_blocks.append(block)

        if matching_blocks:
            return " ".join(b.text for b in matching_blocks)
        return None


class BaseOCREngine(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def process_image(self, image_path: str) -> OCRResult:
        """Process a single image file."""
        pass

    @abstractmethod
    def process_pdf(self, pdf_path: str) -> OCRResult:
        """Process a PDF file."""
        pass

    @abstractmethod
    def process_bytes(self, data: bytes, mime_type: str) -> OCRResult:
        """Process image/PDF from bytes."""
        pass


class TesseractEngine(BaseOCREngine):
    """Tesseract OCR engine implementation."""

    def __init__(self, lang: str = "eng", config: str = ""):
        self.lang = lang
        self.config = config
        self._check_tesseract()

    def _check_tesseract(self):
        """Check if Tesseract is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self.pytesseract = pytesseract
        except Exception:
            self.pytesseract = None

    def process_image(self, image_path: str) -> OCRResult:
        """Process image with Tesseract."""
        if not self.pytesseract:
            return self._create_fallback_result("Tesseract not available")

        try:
            from PIL import Image
            import time

            start_time = time.time()
            image = Image.open(image_path)

            # Get detailed OCR data
            data = self.pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=self.config,
                output_type=self.pytesseract.Output.DICT
            )

            # Get plain text
            raw_text = self.pytesseract.image_to_string(image, lang=self.lang)

            # Parse blocks
            blocks = []
            confidences = []

            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                if text:
                    conf = float(data['conf'][i]) if data['conf'][i] != -1 else 0.0
                    confidences.append(conf)

                    bbox = BoundingBox(
                        left=data['left'][i],
                        top=data['top'][i],
                        width=data['width'][i],
                        height=data['height'][i],
                        page=1
                    )

                    blocks.append(TextBlock(
                        text=text,
                        confidence=conf,
                        bbox=bbox,
                        block_type="word"
                    ))

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            processing_time = int((time.time() - start_time) * 1000)

            return OCRResult(
                raw_text=raw_text,
                blocks=blocks,
                confidence=avg_confidence,
                engine_used="tesseract",
                page_count=1,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            return self._create_fallback_result(f"Tesseract error: {str(e)}")

    def process_pdf(self, pdf_path: str) -> OCRResult:
        """Process PDF with Tesseract (requires pdf2image) or fallback to pdfplumber."""
        import time
        start_time = time.time()

        # Try pdf2image + Tesseract OCR first (for image-based PDFs)
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(pdf_path)

            all_blocks = []
            all_text = []
            confidences = []

            for page_num, image in enumerate(images, 1):
                data = self.pytesseract.image_to_data(
                    image,
                    lang=self.lang,
                    output_type=self.pytesseract.Output.DICT
                )

                page_text = self.pytesseract.image_to_string(image, lang=self.lang)
                all_text.append(f"--- Page {page_num} ---\n{page_text}")

                for i in range(len(data['text'])):
                    text = data['text'][i].strip()
                    if text:
                        conf = float(data['conf'][i]) if data['conf'][i] != -1 else 0.0
                        confidences.append(conf)

                        bbox = BoundingBox(
                            left=data['left'][i],
                            top=data['top'][i],
                            width=data['width'][i],
                            height=data['height'][i],
                            page=page_num
                        )

                        all_blocks.append(TextBlock(
                            text=text,
                            confidence=conf,
                            bbox=bbox,
                            block_type="word"
                        ))

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            processing_time = int((time.time() - start_time) * 1000)

            return OCRResult(
                raw_text="\n".join(all_text),
                blocks=all_blocks,
                confidence=avg_confidence,
                engine_used="tesseract",
                page_count=len(images),
                processing_time_ms=processing_time,
            )

        except ImportError:
            # pdf2image not available, try pdfplumber for text-based PDFs
            pass
        except Exception as e:
            logger.warning(f"pdf2image OCR failed: {e}, trying pdfplumber fallback")

        # Fallback: Use pdfplumber for text-based PDFs
        try:
            import pdfplumber

            all_text = []
            all_blocks = []
            page_count = 0

            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text() or ""
                    if page_text:
                        all_text.append(f"--- Page {page_num} ---\n{page_text}")

                        # Create text blocks from words
                        words = page.extract_words() or []
                        for word in words:
                            all_blocks.append(TextBlock(
                                text=word.get('text', ''),
                                confidence=95.0,  # High confidence for extracted text
                                bbox=BoundingBox(
                                    left=int(word.get('x0', 0)),
                                    top=int(word.get('top', 0)),
                                    width=int(word.get('x1', 0) - word.get('x0', 0)),
                                    height=int(word.get('bottom', 0) - word.get('top', 0)),
                                    page=page_num
                                ),
                                block_type="word"
                            ))

            processing_time = int((time.time() - start_time) * 1000)
            raw_text = "\n".join(all_text)

            if not raw_text.strip():
                return self._create_fallback_result("No text extracted from PDF (may be image-based)")

            return OCRResult(
                raw_text=raw_text,
                blocks=all_blocks,
                confidence=95.0,  # pdfplumber extracts embedded text accurately
                engine_used="pdfplumber",
                page_count=page_count,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            return self._create_fallback_result(f"PDF processing error: {str(e)}")

    def process_bytes(self, data: bytes, mime_type: str) -> OCRResult:
        """Process from bytes."""
        import tempfile
        import os

        suffix = ".pdf" if "pdf" in mime_type.lower() else ".png"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            temp_path = f.name

        try:
            if suffix == ".pdf":
                return self.process_pdf(temp_path)
            else:
                return self.process_image(temp_path)
        finally:
            os.unlink(temp_path)

    def _create_fallback_result(self, error_msg: str) -> OCRResult:
        """Create a fallback result when OCR fails."""
        return OCRResult(
            raw_text="",
            blocks=[],
            confidence=0.0,
            engine_used="tesseract",
            page_count=0,
            metadata={"error": error_msg}
        )


class AWSTextractEngine(BaseOCREngine):
    """AWS Textract OCR engine implementation."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize AWS Textract client."""
        try:
            import boto3
            self.client = boto3.client('textract', region_name=self.region)
        except Exception:
            self.client = None

    def process_image(self, image_path: str) -> OCRResult:
        """Process image with AWS Textract."""
        if not self.client:
            return self._create_fallback_result("AWS Textract client not available")

        try:
            import time

            start_time = time.time()

            with open(image_path, 'rb') as f:
                image_bytes = f.read()

            response = self.client.detect_document_text(
                Document={'Bytes': image_bytes}
            )

            return self._parse_textract_response(response, start_time)

        except Exception as e:
            return self._create_fallback_result(f"Textract error: {str(e)}")

    def process_pdf(self, pdf_path: str) -> OCRResult:
        """Process PDF with AWS Textract (async operation for multi-page)."""
        # For simplicity, use synchronous operation with first page
        # Production would use start_document_text_detection for async
        return self.process_image(pdf_path)

    def process_bytes(self, data: bytes, mime_type: str) -> OCRResult:
        """Process from bytes."""
        if not self.client:
            return self._create_fallback_result("AWS Textract client not available")

        try:
            import time
            start_time = time.time()

            response = self.client.detect_document_text(
                Document={'Bytes': data}
            )

            return self._parse_textract_response(response, start_time)

        except Exception as e:
            return self._create_fallback_result(f"Textract error: {str(e)}")

    def _parse_textract_response(self, response: Dict, start_time: float) -> OCRResult:
        """Parse AWS Textract response."""
        import time

        blocks = []
        text_lines = []
        confidences = []

        for block in response.get('Blocks', []):
            if block['BlockType'] in ['WORD', 'LINE']:
                text = block.get('Text', '')
                confidence = block.get('Confidence', 0.0)
                confidences.append(confidence)

                if block['BlockType'] == 'LINE':
                    text_lines.append(text)

                # Parse bounding box
                bbox = None
                if 'Geometry' in block and 'BoundingBox' in block['Geometry']:
                    geo = block['Geometry']['BoundingBox']
                    bbox = BoundingBox(
                        left=int(geo['Left'] * 1000),
                        top=int(geo['Top'] * 1000),
                        width=int(geo['Width'] * 1000),
                        height=int(geo['Height'] * 1000),
                        page=block.get('Page', 1)
                    )

                blocks.append(TextBlock(
                    text=text,
                    confidence=confidence,
                    bbox=bbox,
                    block_type=block['BlockType'].lower()
                ))

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        processing_time = int((time.time() - start_time) * 1000)

        return OCRResult(
            raw_text="\n".join(text_lines),
            blocks=blocks,
            confidence=avg_confidence,
            engine_used="aws_textract",
            page_count=response.get('DocumentMetadata', {}).get('Pages', 1),
            processing_time_ms=processing_time,
        )

    def _create_fallback_result(self, error_msg: str) -> OCRResult:
        """Create a fallback result when OCR fails."""
        return OCRResult(
            raw_text="",
            blocks=[],
            confidence=0.0,
            engine_used="aws_textract",
            page_count=0,
            metadata={"error": error_msg}
        )


class MockOCREngine(BaseOCREngine):
    """Mock OCR engine for testing and demo when Tesseract isn't available."""

    # Sample W-2 text for demo
    SAMPLE_W2_TEXT = """
Form W-2 Wage and Tax Statement 2025

a Employee's social security number
123-45-6789

b Employer identification number (EIN)
12-3456789

c Employer's name, address, and ZIP code
ACME Corporation
123 Main Street, San Francisco, CA 94102

e Employee's first name and initial Last name
John Q Public

1 Wages, tips, other compensation
$85,000.00

2 Federal income tax withheld
$12,750.00

3 Social security wages
$85,000.00

4 Social security tax withheld
$5,270.00

5 Medicare wages and tips
$85,000.00

6 Medicare tax withheld
$1,232.50

15 State: CA
16 State wages
$85,000.00

17 State income tax
$4,250.00
"""

    SAMPLE_1099_INT_TEXT = """
Form 1099-INT Interest Income 2025

PAYER'S name
First National Bank

PAYER'S TIN
98-7654321

1 Interest income
$1,250.00

4 Federal income tax withheld
$0.00

8 Tax-exempt interest
$0.00
"""

    def __init__(self, mock_responses: Optional[Dict[str, OCRResult]] = None):
        self.mock_responses = mock_responses or {}

    def set_mock_response(self, path_pattern: str, result: OCRResult):
        """Set a mock response for a path pattern."""
        self.mock_responses[path_pattern] = result

    def _detect_document_type(self, data: bytes) -> str:
        """Try to detect document type from file content/name."""
        # For demo, just return W-2 as default
        return "w2"

    def process_image(self, image_path: str) -> OCRResult:
        """Return mock result with sample tax form data."""
        for pattern, result in self.mock_responses.items():
            if pattern in image_path:
                return result

        # Default to W-2 sample for demo
        return OCRResult(
            raw_text=self.SAMPLE_W2_TEXT,
            blocks=[TextBlock(self.SAMPLE_W2_TEXT, 85.0, None, "paragraph")],
            confidence=85.0,
            engine_used="mock",
            page_count=1,
            metadata={"note": "Demo mode - using sample W-2 data"}
        )

    def process_pdf(self, pdf_path: str) -> OCRResult:
        """Return mock result."""
        return self.process_image(pdf_path)

    def process_bytes(self, data: bytes, mime_type: str) -> OCRResult:
        """Return mock result with sample data."""
        return OCRResult(
            raw_text=self.SAMPLE_W2_TEXT,
            blocks=[TextBlock(self.SAMPLE_W2_TEXT, 85.0, None, "paragraph")],
            confidence=85.0,
            engine_used="mock",
            page_count=1,
            metadata={"note": "Demo mode - using sample W-2 data"}
        )


class OCREngineError(Exception):
    """Raised when OCR engine fails in strict mode."""
    pass


class OCREngine:
    """
    Main OCR Engine facade - provides unified interface to multiple OCR backends.

    Usage:
        # Development mode (allows mock fallback)
        engine = OCREngine(engine_type=OCREngineType.TESSERACT)

        # Production mode (raises error if real OCR unavailable)
        engine = OCREngine(engine_type=OCREngineType.TESSERACT, strict_mode=True)

        result = engine.process("path/to/document.pdf")
    """

    def __init__(
        self,
        engine_type: OCREngineType = OCREngineType.TESSERACT,
        fallback_engine: Optional[OCREngineType] = None,
        strict_mode: bool = False,
        **kwargs
    ):
        """
        Initialize OCR Engine.

        Args:
            engine_type: Primary OCR engine to use
            fallback_engine: Optional fallback engine
            strict_mode: If True, raises error when real OCR unavailable (no mock fallback)
            **kwargs: Engine-specific options (lang, config, region)
        """
        self.engine_type = engine_type
        self.fallback_engine_type = fallback_engine
        self.strict_mode = strict_mode
        self.kwargs = kwargs

        self.engine = self._create_engine(engine_type)
        self.fallback = self._create_engine(fallback_engine) if fallback_engine else None

    def _create_engine(self, engine_type: OCREngineType) -> BaseOCREngine:
        """Create OCR engine instance."""
        if engine_type == OCREngineType.TESSERACT:
            engine = TesseractEngine(**{k: v for k, v in self.kwargs.items() if k in ['lang', 'config']})
            # Check if Tesseract is available
            if engine.pytesseract is None:
                if self.strict_mode:
                    raise OCREngineError(
                        "Tesseract OCR is not available. Please install Tesseract:\n"
                        "  macOS: brew install tesseract\n"
                        "  Ubuntu: apt install tesseract-ocr\n"
                        "  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki"
                    )
                print("Warning: Tesseract not available, using mock OCR engine for demo")
                return MockOCREngine()
            return engine
        elif engine_type == OCREngineType.AWS_TEXTRACT:
            engine = AWSTextractEngine(**{k: v for k, v in self.kwargs.items() if k in ['region']})
            if engine.client is None and self.strict_mode:
                raise OCREngineError(
                    "AWS Textract is not available. Please configure AWS credentials:\n"
                    "  pip install boto3\n"
                    "  aws configure"
                )
            return engine
        elif engine_type == OCREngineType.MOCK:
            if self.strict_mode:
                raise OCREngineError(
                    "Mock OCR engine cannot be used in strict mode. "
                    "Please configure a real OCR engine (Tesseract or AWS Textract)."
                )
            return MockOCREngine()
        else:
            # Default: try Tesseract, fall back to mock
            engine = TesseractEngine()
            if engine.pytesseract is None:
                if self.strict_mode:
                    raise OCREngineError(
                        "No OCR engine available. Please install Tesseract or configure AWS Textract."
                    )
                return MockOCREngine()
            return engine

    def process(self, file_path: str) -> OCRResult:
        """
        Process a document file (image or PDF).

        Args:
            file_path: Path to the document file

        Returns:
            OCRResult with extracted text and metadata
        """
        path = Path(file_path)

        if path.suffix.lower() == '.pdf':
            result = self.engine.process_pdf(file_path)
        else:
            result = self.engine.process_image(file_path)

        # Try fallback if primary failed
        if result.confidence < 10 and self.fallback:
            if path.suffix.lower() == '.pdf':
                result = self.fallback.process_pdf(file_path)
            else:
                result = self.fallback.process_image(file_path)

        return result

    def process_bytes(self, data: bytes, mime_type: str) -> OCRResult:
        """
        Process document from bytes.

        Args:
            data: Document bytes
            mime_type: MIME type of the document

        Returns:
            OCRResult with extracted text and metadata
        """
        result = self.engine.process_bytes(data, mime_type)

        if result.confidence < 10 and self.fallback:
            result = self.fallback.process_bytes(data, mime_type)

        return result

    @staticmethod
    def get_available_engines() -> List[OCREngineType]:
        """Get list of available OCR engines on this system."""
        available = []

        # Check Tesseract
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            available.append(OCREngineType.TESSERACT)
        except Exception:
            pass

        # Check AWS
        try:
            import boto3
            available.append(OCREngineType.AWS_TEXTRACT)
        except Exception:
            pass

        # Mock is always available
        available.append(OCREngineType.MOCK)

        return available
