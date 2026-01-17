"""Resilient OCR Processor with retry and circuit breaker patterns.

Wraps the OCR processing functionality with:
- Automatic retry with exponential backoff
- Circuit breaker to prevent cascading failures
- Correlation ID propagation for request tracing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Type

from resilience import (
    async_retry,
    sync_retry,
    RetryConfig,
    RetryExhausted,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    get_circuit_breaker_registry,
)

from .ocr_engine import OCREngine, OCREngineType, OCRResult
from .document_processor import DocumentProcessor, ProcessingResult

logger = logging.getLogger(__name__)


# Default retry configuration for OCR operations
DEFAULT_OCR_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    backoff_multiplier=2.0,
    jitter=0.1,
    retryable_exceptions=(
        IOError,
        TimeoutError,
        ConnectionError,
        OSError,
    ),
    non_retryable_exceptions=(
        ValueError,  # Invalid input
        FileNotFoundError,  # Missing file
    ),
)


# Default circuit breaker configuration
DEFAULT_OCR_CIRCUIT_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    failure_exceptions=(
        IOError,
        TimeoutError,
        ConnectionError,
    ),
    excluded_exceptions=(
        ValueError,
        FileNotFoundError,
    ),
)


@dataclass
class ResilientOCRConfig:
    """Configuration for resilient OCR processing.

    Attributes:
        retry_config: Retry configuration for OCR calls.
        circuit_breaker_config: Circuit breaker configuration.
        enable_circuit_breaker: Whether to use circuit breaker.
        circuit_breaker_name: Name for the circuit breaker instance.
    """
    retry_config: RetryConfig = None
    circuit_breaker_config: CircuitBreakerConfig = None
    enable_circuit_breaker: bool = True
    circuit_breaker_name: str = "ocr_service"

    def __post_init__(self):
        if self.retry_config is None:
            self.retry_config = DEFAULT_OCR_RETRY_CONFIG
        if self.circuit_breaker_config is None:
            self.circuit_breaker_config = DEFAULT_OCR_CIRCUIT_CONFIG


class ResilientOCREngine:
    """OCR Engine wrapper with resilience patterns.

    Provides retry logic and circuit breaker protection for OCR operations.

    Usage:
        engine = ResilientOCREngine()

        # Process with automatic retry and circuit breaker
        result = engine.process("document.pdf")

        # Check circuit breaker state
        if engine.is_circuit_open:
            print("OCR service is temporarily unavailable")
    """

    def __init__(
        self,
        engine_type: OCREngineType = OCREngineType.TESSERACT,
        config: Optional[ResilientOCRConfig] = None,
        fallback_engine: Optional[OCREngineType] = None,
        **engine_kwargs,
    ):
        """Initialize resilient OCR engine.

        Args:
            engine_type: Primary OCR engine to use.
            config: Resilience configuration.
            fallback_engine: Fallback OCR engine type.
            **engine_kwargs: Additional arguments for OCR engine.
        """
        self.config = config or ResilientOCRConfig()
        self._engine = OCREngine(
            engine_type=engine_type,
            fallback_engine=fallback_engine,
            **engine_kwargs,
        )

        # Get or create circuit breaker
        if self.config.enable_circuit_breaker:
            registry = get_circuit_breaker_registry()
            self._circuit_breaker = registry.get(
                self.config.circuit_breaker_name,
                self.config.circuit_breaker_config,
            )
        else:
            self._circuit_breaker = None

    @property
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._circuit_breaker:
            return self._circuit_breaker.is_open
        return False

    @property
    def circuit_state(self) -> Optional[str]:
        """Get current circuit breaker state."""
        if self._circuit_breaker:
            return self._circuit_breaker.state.value
        return None

    def reset_circuit(self) -> None:
        """Reset the circuit breaker to closed state."""
        if self._circuit_breaker:
            self._circuit_breaker.reset()

    @sync_retry(config=DEFAULT_OCR_RETRY_CONFIG)
    def _process_with_retry(self, file_path: str) -> OCRResult:
        """Process with retry logic."""
        return self._engine.process(file_path)

    @sync_retry(config=DEFAULT_OCR_RETRY_CONFIG)
    def _process_bytes_with_retry(
        self,
        data: bytes,
        mime_type: str,
    ) -> OCRResult:
        """Process bytes with retry logic."""
        return self._engine.process_bytes(data, mime_type)

    def process(self, file_path: str) -> OCRResult:
        """Process a document file with resilience patterns.

        Args:
            file_path: Path to the document file.

        Returns:
            OCRResult with extracted text.

        Raises:
            CircuitBreakerOpen: If circuit breaker is open.
            RetryExhausted: If all retries failed.
        """
        if self._circuit_breaker:
            self._circuit_breaker.allow_request()
            try:
                result = self._process_with_retry(file_path)
                self._circuit_breaker.record_success()
                return result
            except RetryExhausted as e:
                self._circuit_breaker.record_failure(
                    e.last_exception or e
                )
                raise
            except Exception as e:
                self._circuit_breaker.record_failure(e)
                raise
        else:
            return self._process_with_retry(file_path)

    def process_bytes(self, data: bytes, mime_type: str) -> OCRResult:
        """Process document bytes with resilience patterns.

        Args:
            data: Document bytes.
            mime_type: MIME type of the document.

        Returns:
            OCRResult with extracted text.

        Raises:
            CircuitBreakerOpen: If circuit breaker is open.
            RetryExhausted: If all retries failed.
        """
        if self._circuit_breaker:
            self._circuit_breaker.allow_request()
            try:
                result = self._process_bytes_with_retry(data, mime_type)
                self._circuit_breaker.record_success()
                return result
            except RetryExhausted as e:
                self._circuit_breaker.record_failure(
                    e.last_exception or e
                )
                raise
            except Exception as e:
                self._circuit_breaker.record_failure(e)
                raise
        else:
            return self._process_bytes_with_retry(data, mime_type)


class ResilientDocumentProcessor:
    """Document processor wrapper with resilience patterns.

    Wraps DocumentProcessor with retry and circuit breaker protection.

    Usage:
        processor = ResilientDocumentProcessor()
        result = processor.process_document("path/to/doc.pdf")
    """

    def __init__(
        self,
        config: Optional[ResilientOCRConfig] = None,
        **processor_kwargs,
    ):
        """Initialize resilient document processor.

        Args:
            config: Resilience configuration.
            **processor_kwargs: Arguments for DocumentProcessor.
        """
        self.config = config or ResilientOCRConfig(
            circuit_breaker_name="document_processor",
        )
        self._processor = DocumentProcessor(**processor_kwargs)

        if self.config.enable_circuit_breaker:
            registry = get_circuit_breaker_registry()
            self._circuit_breaker = registry.get(
                self.config.circuit_breaker_name,
                self.config.circuit_breaker_config,
            )
        else:
            self._circuit_breaker = None

    @property
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._circuit_breaker:
            return self._circuit_breaker.is_open
        return False

    def reset_circuit(self) -> None:
        """Reset the circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.reset()

    @sync_retry(config=DEFAULT_OCR_RETRY_CONFIG)
    def _process_document_with_retry(
        self,
        file_path: str,
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> ProcessingResult:
        """Process document with retry."""
        return self._processor.process_document(
            file_path=file_path,
            document_type=document_type,
            tax_year=tax_year,
        )

    @sync_retry(config=DEFAULT_OCR_RETRY_CONFIG)
    def _process_bytes_with_retry(
        self,
        data: bytes,
        mime_type: str,
        original_filename: str,
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> ProcessingResult:
        """Process bytes with retry."""
        return self._processor.process_bytes(
            data=data,
            mime_type=mime_type,
            original_filename=original_filename,
            document_type=document_type,
            tax_year=tax_year,
        )

    def process_document(
        self,
        file_path: str,
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> ProcessingResult:
        """Process a document file with resilience patterns.

        Args:
            file_path: Path to document file.
            document_type: Optional document type override.
            tax_year: Optional tax year override.

        Returns:
            ProcessingResult with extracted data.

        Raises:
            CircuitBreakerOpen: If circuit breaker is open.
            RetryExhausted: If all retries failed.
        """
        if self._circuit_breaker:
            self._circuit_breaker.allow_request()
            try:
                result = self._process_document_with_retry(
                    file_path, document_type, tax_year
                )
                self._circuit_breaker.record_success()
                return result
            except RetryExhausted as e:
                self._circuit_breaker.record_failure(
                    e.last_exception or e
                )
                raise
            except Exception as e:
                self._circuit_breaker.record_failure(e)
                raise
        else:
            return self._process_document_with_retry(
                file_path, document_type, tax_year
            )

    def process_bytes(
        self,
        data: bytes,
        mime_type: str,
        original_filename: str,
        document_type: Optional[str] = None,
        tax_year: Optional[int] = None,
    ) -> ProcessingResult:
        """Process document bytes with resilience patterns.

        Args:
            data: Document bytes.
            mime_type: MIME type.
            original_filename: Original filename.
            document_type: Optional document type override.
            tax_year: Optional tax year override.

        Returns:
            ProcessingResult with extracted data.

        Raises:
            CircuitBreakerOpen: If circuit breaker is open.
            RetryExhausted: If all retries failed.
        """
        if self._circuit_breaker:
            self._circuit_breaker.allow_request()
            try:
                result = self._process_bytes_with_retry(
                    data, mime_type, original_filename,
                    document_type, tax_year
                )
                self._circuit_breaker.record_success()
                return result
            except RetryExhausted as e:
                self._circuit_breaker.record_failure(
                    e.last_exception or e
                )
                raise
            except Exception as e:
                self._circuit_breaker.record_failure(e)
                raise
        else:
            return self._process_bytes_with_retry(
                data, mime_type, original_filename,
                document_type, tax_year
            )


def get_circuit_breaker_stats() -> Dict[str, Any]:
    """Get statistics for all OCR-related circuit breakers.

    Returns:
        Dictionary with circuit breaker stats.
    """
    registry = get_circuit_breaker_registry()
    return registry.get_all_stats()


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to closed state."""
    registry = get_circuit_breaker_registry()
    registry.reset_all()
