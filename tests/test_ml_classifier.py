"""
Unit tests for ML document classifiers.
"""

import pytest
from unittest.mock import patch, MagicMock

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ml.classifiers.base import (
    ClassificationResult,
    BaseClassifier,
    DOCUMENT_TYPES,
    DOCUMENT_TYPE_DESCRIPTIONS,
)
from ml.classifiers.regex_classifier import RegexClassifier
from ml.settings import MLSettings, get_ml_settings


class TestClassificationResult:
    """Tests for ClassificationResult dataclass."""

    def test_basic_creation(self):
        """Test creating a basic classification result."""
        result = ClassificationResult(
            document_type="w2",
            confidence=0.95,
            classifier_used="test",
        )
        assert result.document_type == "w2"
        assert result.confidence == 0.95
        assert result.classifier_used == "test"

    def test_confidence_clamping(self):
        """Test that confidence is clamped to [0, 1]."""
        result_high = ClassificationResult(
            document_type="w2",
            confidence=1.5,
            classifier_used="test",
        )
        assert result_high.confidence == 1.0

        result_low = ClassificationResult(
            document_type="w2",
            confidence=-0.5,
            classifier_used="test",
        )
        assert result_low.confidence == 0.0

    def test_invalid_document_type_becomes_unknown(self):
        """Test that invalid document types become 'unknown'."""
        result = ClassificationResult(
            document_type="invalid_type",
            confidence=0.9,
            classifier_used="test",
        )
        assert result.document_type == "unknown"

    def test_confidence_percent(self):
        """Test confidence_percent property."""
        result = ClassificationResult(
            document_type="w2",
            confidence=0.85,
            classifier_used="test",
        )
        assert result.confidence_percent == 85.0

    def test_document_type_description(self):
        """Test document_type_description property."""
        result = ClassificationResult(
            document_type="w2",
            confidence=0.9,
            classifier_used="test",
        )
        assert "W-2" in result.document_type_description
        assert "Wage" in result.document_type_description

    def test_to_dict(self):
        """Test to_dict serialization."""
        result = ClassificationResult(
            document_type="1099-int",
            confidence=0.8,
            classifier_used="regex",
            processing_time_ms=5,
            metadata={"test": "value"},
        )
        result_dict = result.to_dict()

        assert result_dict["document_type"] == "1099-int"
        assert result_dict["confidence"] == 0.8
        assert result_dict["confidence_percent"] == 80.0
        assert result_dict["classifier_used"] == "regex"
        assert result_dict["processing_time_ms"] == 5
        assert result_dict["metadata"]["test"] == "value"

    def test_probabilities_normalization(self):
        """Test that probabilities are normalized to sum to 1."""
        result = ClassificationResult(
            document_type="w2",
            confidence=0.9,
            classifier_used="test",
            probabilities={"w2": 0.6, "1099-int": 0.3, "unknown": 0.3},  # Sum > 1
        )
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01


class TestRegexClassifier:
    """Tests for RegexClassifier."""

    @pytest.fixture
    def classifier(self):
        """Create a regex classifier instance."""
        return RegexClassifier()

    def test_classify_w2(self, classifier):
        """Test classifying a W-2 document."""
        text = """
        Form W-2 Wage and Tax Statement
        Employer's identification number: 12-3456789
        Box 1 Wages, tips, other compensation: $75,000.00
        Social security wages: $75,000.00
        Medicare wages and tips: $75,000.00
        """
        result = classifier.classify(text)

        assert result.document_type == "w2"
        assert result.confidence > 0.5
        assert result.classifier_used == "regex"

    def test_classify_1099_int(self, classifier):
        """Test classifying a 1099-INT document."""
        text = """
        Form 1099-INT Interest Income
        Payer's name: First National Bank
        Box 1 Interest income: $1,234.56
        Early withdrawal penalty: $0.00
        Tax-exempt interest: $0.00
        """
        result = classifier.classify(text)

        assert result.document_type == "1099-int"
        assert result.confidence > 0.5

    def test_classify_1099_div(self, classifier):
        """Test classifying a 1099-DIV document."""
        text = """
        Form 1099-DIV Dividends and Distributions
        Total ordinary dividends: $5,000.00
        Qualified dividends: $4,500.00
        Capital gain distributions: $500.00
        """
        result = classifier.classify(text)

        assert result.document_type == "1099-div"
        assert result.confidence > 0.5

    def test_classify_1099_nec(self, classifier):
        """Test classifying a 1099-NEC document."""
        text = """
        Form 1099-NEC Nonemployee Compensation
        Box 1 Nonemployee compensation: $25,000.00
        Payer's TIN: 98-7654321
        """
        result = classifier.classify(text)

        assert result.document_type == "1099-nec"
        assert result.confidence > 0.5

    def test_classify_1098(self, classifier):
        """Test classifying a 1098 document."""
        text = """
        Form 1098 Mortgage Interest Statement
        Mortgage interest received: $12,500.00
        Outstanding mortgage principal: $250,000.00
        """
        result = classifier.classify(text)

        assert result.document_type == "1098"
        assert result.confidence > 0.5

    def test_classify_empty_text(self, classifier):
        """Test classifying empty text."""
        result = classifier.classify("")

        assert result.document_type == "unknown"
        assert result.confidence == 0.0
        assert result.metadata.get("reason") == "empty_text"

    def test_classify_unknown_document(self, classifier):
        """Test classifying unrecognized text."""
        text = "This is just some random text without any tax form indicators."
        result = classifier.classify(text)

        assert result.document_type == "unknown"
        assert result.confidence == 0.0

    def test_classify_k1(self, classifier):
        """Test classifying a Schedule K-1 document."""
        text = """
        Schedule K-1 Partner's Share of Income
        Partner's share of income: $10,000.00
        Ordinary business income: $8,000.00
        """
        result = classifier.classify(text)

        assert result.document_type == "k1"
        assert result.confidence >= 0.5

    def test_preprocess_text(self, classifier):
        """Test text preprocessing."""
        text = "  FORM  W-2   WAGE   AND   TAX   STATEMENT  "
        processed = classifier.preprocess_text(text)

        assert "form w-2" in processed
        assert "  " not in processed  # No double spaces

    def test_processing_time_recorded(self, classifier):
        """Test that processing time is recorded."""
        text = "Form W-2 Wage and Tax Statement"
        result = classifier.classify(text)

        assert result.processing_time_ms >= 0

    def test_get_supported_types(self, classifier):
        """Test getting supported document types."""
        supported = classifier.get_supported_types()

        assert "w2" in supported
        assert "1099-int" in supported
        assert "1099-div" in supported


class TestMLSettings:
    """Tests for MLSettings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = MLSettings()

        assert settings.primary_classifier == "ensemble"
        assert settings.fallback_enabled is True
        assert settings.openai_model == "gpt-4o-mini"
        assert settings.min_confidence_threshold == 0.7
        assert settings.high_confidence_threshold == 0.9

    def test_settings_from_env(self, monkeypatch):
        """Test loading settings from environment variables."""
        monkeypatch.setenv("ML_PRIMARY_CLASSIFIER", "openai")
        monkeypatch.setenv("ML_FALLBACK_ENABLED", "false")
        monkeypatch.setenv("ML_MIN_CONFIDENCE_THRESHOLD", "0.8")

        # Clear cached settings
        get_ml_settings.cache_clear()

        settings = MLSettings()

        assert settings.primary_classifier == "openai"
        assert settings.fallback_enabled is False
        assert settings.min_confidence_threshold == 0.8

    def test_get_ml_settings_caching(self):
        """Test that get_ml_settings returns cached instance."""
        # Clear cache first
        get_ml_settings.cache_clear()

        settings1 = get_ml_settings()
        settings2 = get_ml_settings()

        assert settings1 is settings2


class TestDocumentTypes:
    """Tests for document type constants."""

    def test_all_types_have_descriptions(self):
        """Test that all document types have descriptions."""
        for doc_type in DOCUMENT_TYPES:
            assert doc_type in DOCUMENT_TYPE_DESCRIPTIONS

    def test_document_types_list(self):
        """Test document types list contains expected types."""
        expected_types = [
            "w2", "w2g", "1099-int", "1099-div", "1099-nec", "1099-misc",
            "1099-b", "1099-r", "1099-g", "1099-k", "1099-sa", "1099-q",
            "1099-c", "1099-s", "1099-oid", "1099-ltc", "1099-patr",
            "1098", "1098-e", "1098-t", "k1", "1095-a", "1095-b", "1095-c",
            "ssa-1099", "rrb-1099", "5498", "5498-sa", "unknown"
        ]
        for expected in expected_types:
            assert expected in DOCUMENT_TYPES


class TestOpenAIClassifier:
    """Tests for OpenAIClassifier with mocked API."""

    def test_classify_without_api_key(self):
        """Test behavior when API key is not configured."""
        from ml.classifiers.openai_classifier import OpenAIClassifier

        # Temporarily clear the API key
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            classifier = OpenAIClassifier(api_key=None)

            assert classifier.is_available() is False

            result = classifier.classify("Form W-2 Test")
            assert result.document_type == "unknown"
            assert result.metadata.get("reason") == "api_key_not_configured"

    def test_classify_with_mocked_api(self):
        """Test classification with mocked OpenAI API."""
        from ml.classifiers.openai_classifier import OpenAIClassifier

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"document_type": "w2", "confidence": 0.95, "reasoning": "Form W-2 header detected", "key_indicators": ["Form W-2"]}'
                )
            )
        ]
        mock_response.usage = MagicMock(total_tokens=100)

        with patch.object(OpenAIClassifier, 'client', create=True) as mock_client:
            mock_client.chat.completions.create.return_value = mock_response

            classifier = OpenAIClassifier(api_key="test-key")
            classifier._client = mock_client

            result = classifier.classify("Form W-2 Wage and Tax Statement")

            assert result.document_type == "w2"
            assert result.confidence == 0.95
            assert result.classifier_used == "openai"

    def test_classify_empty_text(self):
        """Test classifying empty text."""
        from ml.classifiers.openai_classifier import OpenAIClassifier

        classifier = OpenAIClassifier(api_key="test-key")
        result = classifier.classify("")

        assert result.document_type == "unknown"
        assert result.confidence == 0.0
        assert result.metadata.get("reason") == "empty_text"


class TestTFIDFClassifier:
    """Tests for TFIDFClassifier."""

    def test_classifier_not_available_without_models(self):
        """Test that classifier reports unavailable when models don't exist."""
        from ml.classifiers.tfidf_classifier import TFIDFClassifier

        classifier = TFIDFClassifier(model_path="/nonexistent/path")
        assert classifier.is_available() is False

    def test_classify_without_models(self):
        """Test classification returns unknown when models not loaded."""
        from ml.classifiers.tfidf_classifier import TFIDFClassifier

        classifier = TFIDFClassifier(model_path="/nonexistent/path")
        result = classifier.classify("Form W-2 Test")

        assert result.document_type == "unknown"
        assert result.metadata.get("reason") == "models_not_loaded"


class TestTFIDFClassifierWithTrainedModels:
    """Tests for TFIDFClassifier with trained models."""

    @pytest.fixture
    def tfidf_classifier(self):
        """Create TF-IDF classifier with default model path."""
        from ml.classifiers.tfidf_classifier import TFIDFClassifier
        return TFIDFClassifier()

    def test_classifier_is_available(self, tfidf_classifier):
        """Test that classifier is available with trained models."""
        # Skip if models not available
        if not tfidf_classifier.is_available():
            pytest.skip("TF-IDF models not available")
        assert tfidf_classifier.is_available() is True

    def test_classify_w2(self, tfidf_classifier):
        """Test classifying W-2 document."""
        if not tfidf_classifier.is_available():
            pytest.skip("TF-IDF models not available")

        w2_text = """
        Form W-2 Wage and Tax Statement 2025
        Employee's social security number 123-45-6789
        Employer identification number (EIN) 12-3456789
        Wages, tips, other compensation: 75,000.00
        Federal income tax withheld: 12,000.00
        """
        result = tfidf_classifier.classify(w2_text)

        assert result.document_type == "w2"
        assert result.confidence > 0.5
        assert result.classifier_used == "tfidf"
        assert result.processing_time_ms >= 0

    def test_classify_1099_int(self, tfidf_classifier):
        """Test classifying 1099-INT document."""
        if not tfidf_classifier.is_available():
            pytest.skip("TF-IDF models not available")

        text = """
        Form 1099-INT Interest Income
        Payer's name: Big Bank Corp
        Interest income: $1,234.56
        Federal income tax withheld: $0.00
        """
        result = tfidf_classifier.classify(text)

        assert result.document_type == "1099-int"
        assert result.confidence > 0.4
        assert result.classifier_used == "tfidf"

    def test_classify_1099_div(self, tfidf_classifier):
        """Test classifying 1099-DIV document."""
        if not tfidf_classifier.is_available():
            pytest.skip("TF-IDF models not available")

        text = """
        Form 1099-DIV Dividends and Distributions
        Payer's name: Investment Corp
        Total ordinary dividends: $500.00
        Qualified dividends: $400.00
        """
        result = tfidf_classifier.classify(text)

        assert result.document_type == "1099-div"
        assert result.confidence > 0.4

    def test_classify_batch(self, tfidf_classifier):
        """Test batch classification."""
        if not tfidf_classifier.is_available():
            pytest.skip("TF-IDF models not available")

        texts = [
            "Form W-2 Wage and Tax Statement wages salary",
            "Form 1099-INT Interest Income bank interest",
            "Form 1099-DIV Dividends distributions qualified",
        ]
        results = tfidf_classifier.classify_batch(texts)

        assert len(results) == 3
        assert results[0].document_type == "w2"
        assert results[1].document_type == "1099-int"
        assert results[2].document_type == "1099-div"

    def test_probabilities_sum_to_one(self, tfidf_classifier):
        """Test that probabilities sum to approximately 1."""
        if not tfidf_classifier.is_available():
            pytest.skip("TF-IDF models not available")

        result = tfidf_classifier.classify("Form W-2 Wage and Tax Statement")

        if result.probabilities:
            total = sum(result.probabilities.values())
            assert 0.99 <= total <= 1.01  # Allow small floating point error

    def test_top_3_predictions_in_metadata(self, tfidf_classifier):
        """Test that top 3 predictions are in metadata."""
        if not tfidf_classifier.is_available():
            pytest.skip("TF-IDF models not available")

        result = tfidf_classifier.classify("Form W-2 Wage and Tax Statement")

        assert "top_3" in result.metadata
        assert len(result.metadata["top_3"]) == 3
        # Top 3 should be tuples of (doc_type, probability)
        for item in result.metadata["top_3"]:
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], float)


class TestEnsembleClassifier:
    """Tests for EnsembleClassifier."""

    def test_ensemble_uses_regex_as_fallback(self):
        """Test that ensemble falls back to regex when other classifiers unavailable."""
        from ml.classifiers.ensemble_classifier import EnsembleClassifier

        # Create ensemble without OpenAI key and without TF-IDF models
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            classifier = EnsembleClassifier()

            # Should have regex in the chain
            assert "regex" in classifier.get_available_classifiers()

            # Should still classify correctly using regex
            result = classifier.classify("Form W-2 Wage and Tax Statement")
            assert result.document_type == "w2"
            assert result.confidence > 0

    def test_ensemble_empty_text(self):
        """Test ensemble with empty text."""
        from ml.classifiers.ensemble_classifier import EnsembleClassifier

        classifier = EnsembleClassifier()
        result = classifier.classify("")

        assert result.document_type == "unknown"
        assert result.confidence == 0.0
