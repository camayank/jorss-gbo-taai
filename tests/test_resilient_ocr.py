"""Tests for resilient OCR processors with retry and circuit breaker."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

from resilience import (
    RetryConfig,
    RetryExhausted,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    get_circuit_breaker_registry,
)
from services.ocr.resilient_processor import (
    ResilientOCREngine,
    ResilientDocumentProcessor,
    ResilientOCRConfig,
    DEFAULT_OCR_RETRY_CONFIG,
    DEFAULT_OCR_CIRCUIT_CONFIG,
    get_circuit_breaker_stats,
    reset_all_circuit_breakers,
)


class TestResilientOCRConfig:
    """Tests for ResilientOCRConfig dataclass."""

    def test_default_values(self):
        """Config has sensible defaults."""
        config = ResilientOCRConfig()

        assert config.retry_config is not None
        assert config.circuit_breaker_config is not None
        assert config.enable_circuit_breaker is True
        assert config.circuit_breaker_name == "ocr_service"

    def test_uses_default_retry_config(self):
        """Uses DEFAULT_OCR_RETRY_CONFIG when not specified."""
        config = ResilientOCRConfig()

        assert config.retry_config.max_attempts == DEFAULT_OCR_RETRY_CONFIG.max_attempts
        assert config.retry_config.base_delay == DEFAULT_OCR_RETRY_CONFIG.base_delay

    def test_uses_default_circuit_config(self):
        """Uses DEFAULT_OCR_CIRCUIT_CONFIG when not specified."""
        config = ResilientOCRConfig()

        assert config.circuit_breaker_config.failure_threshold == DEFAULT_OCR_CIRCUIT_CONFIG.failure_threshold
        assert config.circuit_breaker_config.timeout == DEFAULT_OCR_CIRCUIT_CONFIG.timeout

    def test_custom_config(self):
        """Can provide custom configurations."""
        custom_retry = RetryConfig(max_attempts=5, base_delay=2.0)
        custom_circuit = CircuitBreakerConfig(failure_threshold=10)

        config = ResilientOCRConfig(
            retry_config=custom_retry,
            circuit_breaker_config=custom_circuit,
            enable_circuit_breaker=False,
            circuit_breaker_name="custom_ocr",
        )

        assert config.retry_config.max_attempts == 5
        assert config.circuit_breaker_config.failure_threshold == 10
        assert config.enable_circuit_breaker is False
        assert config.circuit_breaker_name == "custom_ocr"


class TestDefaultConfigs:
    """Tests for default configuration values."""

    def test_default_retry_config_values(self):
        """Default retry config has expected values."""
        config = DEFAULT_OCR_RETRY_CONFIG

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.backoff_multiplier == 2.0
        assert config.jitter == 0.1

    def test_default_retry_retryable_exceptions(self):
        """Default retry config has correct retryable exceptions."""
        config = DEFAULT_OCR_RETRY_CONFIG

        assert IOError in config.retryable_exceptions
        assert TimeoutError in config.retryable_exceptions
        assert ConnectionError in config.retryable_exceptions
        assert OSError in config.retryable_exceptions

    def test_default_retry_non_retryable_exceptions(self):
        """Default retry config has correct non-retryable exceptions."""
        config = DEFAULT_OCR_RETRY_CONFIG

        assert ValueError in config.non_retryable_exceptions
        assert FileNotFoundError in config.non_retryable_exceptions

    def test_default_circuit_config_values(self):
        """Default circuit breaker config has expected values."""
        config = DEFAULT_OCR_CIRCUIT_CONFIG

        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60.0


class TestResilientOCREngine:
    """Tests for ResilientOCREngine."""

    @pytest.fixture(autouse=True)
    def reset_circuit_breakers(self):
        """Reset all circuit breakers before each test."""
        reset_all_circuit_breakers()
        yield
        reset_all_circuit_breakers()

    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        with patch("services.ocr.resilient_processor.OCREngine") as mock:
            engine_instance = MagicMock()
            mock.return_value = engine_instance
            yield engine_instance

    def test_initialization_default_config(self, mock_ocr_engine):
        """Engine initializes with default config."""
        engine = ResilientOCREngine()

        assert engine.config is not None
        assert engine.config.enable_circuit_breaker is True

    def test_initialization_custom_config(self, mock_ocr_engine):
        """Engine initializes with custom config."""
        config = ResilientOCRConfig(
            enable_circuit_breaker=False,
            circuit_breaker_name="test_engine",
        )
        engine = ResilientOCREngine(config=config)

        assert engine.config == config
        assert engine._circuit_breaker is None

    def test_is_circuit_open_false_when_closed(self, mock_ocr_engine):
        """is_circuit_open returns False when circuit is closed."""
        engine = ResilientOCREngine()

        assert engine.is_circuit_open is False

    def test_is_circuit_open_false_when_disabled(self, mock_ocr_engine):
        """is_circuit_open returns False when circuit breaker disabled."""
        config = ResilientOCRConfig(enable_circuit_breaker=False)
        engine = ResilientOCREngine(config=config)

        assert engine.is_circuit_open is False

    def test_circuit_state_closed(self, mock_ocr_engine):
        """circuit_state returns 'closed' initially."""
        engine = ResilientOCREngine()

        assert engine.circuit_state == "closed"

    def test_circuit_state_none_when_disabled(self, mock_ocr_engine):
        """circuit_state returns None when circuit breaker disabled."""
        config = ResilientOCRConfig(enable_circuit_breaker=False)
        engine = ResilientOCREngine(config=config)

        assert engine.circuit_state is None

    def test_reset_circuit(self, mock_ocr_engine):
        """reset_circuit resets the circuit breaker."""
        engine = ResilientOCREngine()

        # Trigger failures to open circuit
        if engine._circuit_breaker:
            for _ in range(10):
                engine._circuit_breaker.record_failure(IOError("test"))

        engine.reset_circuit()
        assert engine.circuit_state == "closed"

    def test_process_success(self, mock_ocr_engine):
        """process returns result on success."""
        mock_result = MagicMock()
        mock_result.text = "Extracted text"
        mock_ocr_engine.process.return_value = mock_result

        config = ResilientOCRConfig(enable_circuit_breaker=False)
        engine = ResilientOCREngine(config=config)
        result = engine.process("test.pdf")

        assert result == mock_result
        mock_ocr_engine.process.assert_called_once_with("test.pdf")

    def test_process_bytes_success(self, mock_ocr_engine):
        """process_bytes returns result on success."""
        mock_result = MagicMock()
        mock_result.text = "Extracted text"
        mock_ocr_engine.process_bytes.return_value = mock_result

        config = ResilientOCRConfig(enable_circuit_breaker=False)
        engine = ResilientOCREngine(config=config)
        result = engine.process_bytes(b"data", "application/pdf")

        assert result == mock_result
        mock_ocr_engine.process_bytes.assert_called_once_with(b"data", "application/pdf")

    def test_process_with_circuit_breaker_open_raises(self, mock_ocr_engine):
        """process raises CircuitBreakerOpen when circuit is open."""
        engine = ResilientOCREngine()

        # Open the circuit breaker
        for _ in range(10):
            engine._circuit_breaker.record_failure(IOError("test"))

        with pytest.raises(CircuitBreakerOpen):
            engine.process("test.pdf")


class TestResilientDocumentProcessor:
    """Tests for ResilientDocumentProcessor."""

    @pytest.fixture(autouse=True)
    def reset_circuit_breakers(self):
        """Reset all circuit breakers before each test."""
        reset_all_circuit_breakers()
        yield
        reset_all_circuit_breakers()

    @pytest.fixture
    def mock_doc_processor(self):
        """Create a mock document processor."""
        with patch("services.ocr.resilient_processor.DocumentProcessor") as mock:
            processor_instance = MagicMock()
            mock.return_value = processor_instance
            yield processor_instance

    def test_initialization_default_config(self, mock_doc_processor):
        """Processor initializes with default config."""
        processor = ResilientDocumentProcessor()

        assert processor.config is not None
        assert processor.config.circuit_breaker_name == "document_processor"

    def test_initialization_custom_config(self, mock_doc_processor):
        """Processor initializes with custom config."""
        config = ResilientOCRConfig(
            enable_circuit_breaker=False,
            circuit_breaker_name="custom_processor",
        )
        processor = ResilientDocumentProcessor(config=config)

        assert processor.config == config
        assert processor._circuit_breaker is None

    def test_is_circuit_open_false_when_closed(self, mock_doc_processor):
        """is_circuit_open returns False when circuit is closed."""
        processor = ResilientDocumentProcessor()

        assert processor.is_circuit_open is False

    def test_reset_circuit(self, mock_doc_processor):
        """reset_circuit resets the circuit breaker."""
        processor = ResilientDocumentProcessor()

        # Trigger failures
        if processor._circuit_breaker:
            for _ in range(10):
                processor._circuit_breaker.record_failure(IOError("test"))

        processor.reset_circuit()
        assert processor.is_circuit_open is False

    def test_process_document_success(self, mock_doc_processor):
        """process_document returns result on success."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_doc_processor.process_document.return_value = mock_result

        config = ResilientOCRConfig(enable_circuit_breaker=False)
        processor = ResilientDocumentProcessor(config=config)
        result = processor.process_document("test.pdf", document_type="w2", tax_year=2024)

        assert result == mock_result
        mock_doc_processor.process_document.assert_called_once_with(
            file_path="test.pdf",
            document_type="w2",
            tax_year=2024,
        )

    def test_process_bytes_success(self, mock_doc_processor):
        """process_bytes returns result on success."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_doc_processor.process_bytes.return_value = mock_result

        config = ResilientOCRConfig(enable_circuit_breaker=False)
        processor = ResilientDocumentProcessor(config=config)
        result = processor.process_bytes(
            data=b"data",
            mime_type="application/pdf",
            original_filename="test.pdf",
            document_type="1099",
            tax_year=2024,
        )

        assert result == mock_result
        mock_doc_processor.process_bytes.assert_called_once()

    def test_process_document_with_circuit_breaker_open_raises(self, mock_doc_processor):
        """process_document raises CircuitBreakerOpen when circuit is open."""
        processor = ResilientDocumentProcessor()

        # Open the circuit breaker
        for _ in range(10):
            processor._circuit_breaker.record_failure(IOError("test"))

        with pytest.raises(CircuitBreakerOpen):
            processor.process_document("test.pdf")


class TestCircuitBreakerUtilities:
    """Tests for circuit breaker utility functions."""

    @pytest.fixture(autouse=True)
    def reset_circuit_breakers(self):
        """Reset all circuit breakers before each test."""
        reset_all_circuit_breakers()
        yield
        reset_all_circuit_breakers()

    def test_get_circuit_breaker_stats(self):
        """get_circuit_breaker_stats returns stats dict."""
        # Create some circuit breakers by instantiating engines
        with patch("services.ocr.resilient_processor.OCREngine"):
            engine1 = ResilientOCREngine(config=ResilientOCRConfig(
                circuit_breaker_name="test_engine_1"
            ))
            engine2 = ResilientOCREngine(config=ResilientOCRConfig(
                circuit_breaker_name="test_engine_2"
            ))

        stats = get_circuit_breaker_stats()

        assert isinstance(stats, dict)
        assert "test_engine_1" in stats
        assert "test_engine_2" in stats

    def test_reset_all_circuit_breakers(self):
        """reset_all_circuit_breakers resets all breakers."""
        with patch("services.ocr.resilient_processor.OCREngine"):
            engine = ResilientOCREngine(config=ResilientOCRConfig(
                circuit_breaker_name="reset_test_engine"
            ))

        # Open the circuit
        if engine._circuit_breaker:
            for _ in range(10):
                engine._circuit_breaker.record_failure(IOError("test"))

            assert engine.is_circuit_open is True

        reset_all_circuit_breakers()

        # Should be closed now
        assert engine.circuit_state == "closed"


class TestRetryBehavior:
    """Tests for retry behavior in resilient processors."""

    @pytest.fixture(autouse=True)
    def reset_circuit_breakers(self):
        """Reset all circuit breakers before each test."""
        reset_all_circuit_breakers()
        yield
        reset_all_circuit_breakers()

    def test_retries_on_io_error(self):
        """Processor retries on IOError."""
        with patch("services.ocr.resilient_processor.OCREngine") as mock_class:
            mock_engine = MagicMock()
            mock_class.return_value = mock_engine

            # Fail twice, then succeed
            mock_result = MagicMock()
            mock_engine.process.side_effect = [
                IOError("First failure"),
                IOError("Second failure"),
                mock_result,
            ]

            config = ResilientOCRConfig(
                enable_circuit_breaker=False,
                retry_config=RetryConfig(
                    max_attempts=3,
                    base_delay=0.01,  # Fast retries for testing
                    retryable_exceptions=(IOError,),
                ),
            )
            engine = ResilientOCREngine(config=config)
            result = engine.process("test.pdf")

            assert result == mock_result
            assert mock_engine.process.call_count == 3

    def test_does_not_retry_on_value_error(self):
        """Processor does not retry on ValueError."""
        with patch("services.ocr.resilient_processor.OCREngine") as mock_class:
            mock_engine = MagicMock()
            mock_class.return_value = mock_engine
            mock_engine.process.side_effect = ValueError("Invalid input")

            config = ResilientOCRConfig(
                enable_circuit_breaker=False,
                retry_config=RetryConfig(
                    max_attempts=3,
                    base_delay=0.01,
                    non_retryable_exceptions=(ValueError,),
                ),
            )
            engine = ResilientOCREngine(config=config)

            with pytest.raises(ValueError):
                engine.process("test.pdf")

            # Should only be called once (no retries)
            assert mock_engine.process.call_count == 1

    def test_exhausts_retries_raises_retry_exhausted(self):
        """Raises RetryExhausted when all retries fail."""
        with patch("services.ocr.resilient_processor.OCREngine") as mock_class:
            mock_engine = MagicMock()
            mock_class.return_value = mock_engine
            mock_engine.process.side_effect = IOError("Persistent failure")

            config = ResilientOCRConfig(
                enable_circuit_breaker=False,
                retry_config=RetryConfig(
                    max_attempts=3,
                    base_delay=0.01,
                    retryable_exceptions=(IOError,),
                ),
            )
            engine = ResilientOCREngine(config=config)

            with pytest.raises(RetryExhausted):
                engine.process("test.pdf")

            assert mock_engine.process.call_count == 3
