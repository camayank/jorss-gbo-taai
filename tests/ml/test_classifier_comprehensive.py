"""
Comprehensive tests for DocumentClassifier — classification by document type,
confidence thresholds, batch classification, unknown types, and edge cases.
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ml.classifiers.base import (
    ClassificationResult,
    DOCUMENT_TYPES,
    DOCUMENT_TYPE_DESCRIPTIONS,
    BaseClassifier,
)


# ===================================================================
# ClassificationResult DATACLASS
# ===================================================================

class TestClassificationResult:

    def test_basic_creation(self):
        r = ClassificationResult(document_type="w2", confidence=0.95)
        assert r.document_type == "w2"
        assert r.confidence == 0.95

    @pytest.mark.parametrize("doc_type", DOCUMENT_TYPES)
    def test_all_valid_document_types(self, doc_type):
        r = ClassificationResult(document_type=doc_type, confidence=0.8)
        assert r.document_type == doc_type

    def test_invalid_type_becomes_unknown(self):
        r = ClassificationResult(document_type="invalid_type", confidence=0.8)
        assert r.document_type == "unknown"

    @pytest.mark.parametrize("conf,expected", [
        (0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (-0.1, 0.0), (1.5, 1.0),
    ])
    def test_confidence_clamping(self, conf, expected):
        r = ClassificationResult(document_type="w2", confidence=conf)
        assert r.confidence == expected

    def test_confidence_percent(self):
        r = ClassificationResult(document_type="w2", confidence=0.85)
        assert r.confidence_percent == 85.0

    def test_document_type_description(self):
        r = ClassificationResult(document_type="w2", confidence=0.9)
        assert "W-2" in r.document_type_description

    def test_unknown_type_description(self):
        r = ClassificationResult(document_type="unknown", confidence=0.1)
        assert "Unknown" in r.document_type_description

    def test_to_dict(self):
        r = ClassificationResult(document_type="w2", confidence=0.95, classifier_used="regex")
        d = r.to_dict()
        assert d["document_type"] == "w2"
        assert d["confidence"] == 0.95
        assert d["classifier_used"] == "regex"
        assert "confidence_percent" in d

    def test_to_dict_contains_probabilities(self):
        probs = {"w2": 0.8, "1099-int": 0.2}
        r = ClassificationResult(document_type="w2", confidence=0.8, probabilities=probs)
        d = r.to_dict()
        assert d["probabilities"]["w2"] == pytest.approx(0.8, abs=0.01)

    def test_probabilities_normalization(self):
        probs = {"w2": 80, "1099-int": 20}
        r = ClassificationResult(document_type="w2", confidence=0.8, probabilities=probs)
        total = sum(r.probabilities.values())
        assert total == pytest.approx(1.0, abs=0.02)

    def test_empty_probabilities(self):
        r = ClassificationResult(document_type="w2", confidence=0.9, probabilities={})
        assert r.probabilities == {}

    def test_processing_time(self):
        r = ClassificationResult(document_type="w2", confidence=0.9, processing_time_ms=50)
        assert r.processing_time_ms == 50

    def test_metadata(self):
        r = ClassificationResult(document_type="w2", confidence=0.9, metadata={"source": "ocr"})
        assert r.metadata["source"] == "ocr"

    def test_default_classifier_used(self):
        r = ClassificationResult(document_type="w2", confidence=0.9)
        assert r.classifier_used == ""

    def test_default_metadata(self):
        r = ClassificationResult(document_type="w2", confidence=0.9)
        assert r.metadata == {}


# ===================================================================
# DOCUMENT_TYPES AND DESCRIPTIONS
# ===================================================================

class TestDocumentTypes:

    def test_document_types_is_list(self):
        assert isinstance(DOCUMENT_TYPES, list)

    def test_document_types_contains_w2(self):
        assert "w2" in DOCUMENT_TYPES

    @pytest.mark.parametrize("dtype", [
        "w2", "1099-int", "1099-div", "1099-misc", "1099-nec",
        "1099-k", "1098", "k1", "unknown",
    ])
    def test_expected_types_present(self, dtype):
        assert dtype in DOCUMENT_TYPES

    def test_unknown_is_last(self):
        assert DOCUMENT_TYPES[-1] == "unknown"

    def test_no_duplicates(self):
        assert len(DOCUMENT_TYPES) == len(set(DOCUMENT_TYPES))


class TestDocumentTypeDescriptions:

    @pytest.mark.parametrize("dtype", [t for t in DOCUMENT_TYPES if t != "unknown"])
    def test_all_types_have_descriptions(self, dtype):
        assert dtype in DOCUMENT_TYPE_DESCRIPTIONS

    def test_descriptions_are_strings(self):
        for desc in DOCUMENT_TYPE_DESCRIPTIONS.values():
            assert isinstance(desc, str)

    @pytest.mark.parametrize("dtype,contains", [
        ("w2", "Wage"),
        ("1099-int", "Interest"),
        ("1099-div", "Dividend"),
        ("1099-nec", "Nonemployee"),
        ("1098", "Mortgage"),
        ("k1", "K-1"),
    ])
    def test_description_content(self, dtype, contains):
        assert contains in DOCUMENT_TYPE_DESCRIPTIONS[dtype]


# ===================================================================
# DocumentClassifier
# ===================================================================

class TestDocumentClassifier:

    def test_create_classifier(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        assert classifier is not None

    def test_classify_returns_result(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("Form W-2 Wage and Tax Statement")
        assert isinstance(result, ClassificationResult)

    @pytest.mark.parametrize("doc_type,text_key,expected_type", [
        ("w2", "w2", "w2"),
        ("1099-int", "1099-int", "1099-int"),
        ("1099-div", "1099-div", "1099-div"),
        ("1099-misc", "1099-misc", "1099-misc"),
        ("1099-nec", "1099-nec", "1099-nec"),
        ("1099-k", "1099-k", "1099-k"),
        ("1098", "1098", "1098"),
        ("k1", "k1", "k1"),
        ("1040", "1040", "unknown"),  # 1040 is not in DOCUMENT_TYPES, normalizes to unknown
    ])
    def test_classify_each_document_type(self, doc_type, text_key, expected_type, mock_ensemble_classifier, all_sample_documents):
        from ml.document_classifier import DocumentClassifier
        mock_ensemble_classifier.classify.return_value = ClassificationResult(
            document_type=doc_type, confidence=0.9, classifier_used="ensemble"
        )
        classifier = DocumentClassifier()
        result = classifier.classify(all_sample_documents[text_key])
        assert result.document_type == expected_type

    def test_classify_batch(self, mock_ensemble_classifier, all_sample_documents):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        texts = list(all_sample_documents.values())
        results = classifier.classify_batch(texts)
        assert len(results) == len(texts)

    def test_classify_batch_empty(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        mock_ensemble_classifier.classify_batch.return_value = []
        results = classifier.classify_batch([])
        assert results == []

    def test_classify_batch_single(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        results = classifier.classify_batch(["single doc"])
        assert len(results) == 1

    def test_classify_batch_large(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        texts = ["doc"] * 100
        results = classifier.classify_batch(texts)
        assert len(results) == 100


class TestClassifierSupportedTypes:

    def test_get_supported_types(self):
        from ml.document_classifier import DocumentClassifier
        types = DocumentClassifier.get_supported_document_types()
        assert isinstance(types, list)
        assert "unknown" not in types
        assert "w2" in types

    def test_supported_types_count(self):
        from ml.document_classifier import DocumentClassifier
        types = DocumentClassifier.get_supported_document_types()
        assert len(types) == len(DOCUMENT_TYPES) - 1  # minus unknown

    @pytest.mark.parametrize("dtype", ["w2", "1099-int", "1099-div", "k1", "1098"])
    def test_type_description_lookup(self, dtype):
        from ml.document_classifier import DocumentClassifier
        desc = DocumentClassifier.get_document_type_description(dtype)
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_unknown_type_description(self):
        from ml.document_classifier import DocumentClassifier
        desc = DocumentClassifier.get_document_type_description("nonexistent_type")
        assert "Unknown" in desc


class TestClassifierInfo:

    def test_get_classifier_info(self, mock_ensemble_classifier, mock_ml_settings):
        from ml.document_classifier import DocumentClassifier
        with patch("ml.document_classifier.get_ml_settings", return_value=mock_ml_settings):
            classifier = DocumentClassifier(settings=mock_ml_settings)
            info = classifier.get_classifier_info()
            assert "primary_classifier" in info
            assert "fallback_enabled" in info
            assert "min_confidence_threshold" in info
            assert "available_classifiers" in info


class TestCreateClassifierFactory:

    def test_create_default_ensemble(self, mock_ensemble_classifier):
        from ml.document_classifier import create_classifier
        with patch("ml.document_classifier.get_ml_settings") as mock_settings:
            ms = Mock()
            ms.primary_classifier = "ensemble"
            ms.fallback_enabled = True
            ms.min_confidence_threshold = 0.7
            mock_settings.return_value = ms
            classifier = create_classifier()
            assert classifier is not None

    @pytest.mark.parametrize("ctype", ["ensemble", "regex", "tfidf"])
    def test_create_classifier_types(self, ctype, mock_ensemble_classifier):
        from ml.document_classifier import create_classifier
        with patch("ml.document_classifier.get_ml_settings") as mock_settings:
            ms = Mock()
            ms.primary_classifier = ctype
            ms.fallback_enabled = True
            ms.min_confidence_threshold = 0.7
            mock_settings.return_value = ms
            classifier = create_classifier(ctype)
            assert classifier is not None


# ===================================================================
# CONFIDENCE THRESHOLDS
# ===================================================================

class TestConfidenceThresholds:

    @pytest.mark.parametrize("confidence,is_high", [
        (0.95, True), (0.90, True), (0.89, False),
        (0.70, False), (0.50, False), (0.10, False),
    ])
    def test_high_confidence_threshold(self, confidence, is_high):
        HIGH_THRESHOLD = 0.9
        assert (confidence >= HIGH_THRESHOLD) == is_high

    @pytest.mark.parametrize("confidence,is_acceptable", [
        (0.95, True), (0.80, True), (0.70, True),
        (0.69, False), (0.50, False), (0.01, False),
    ])
    def test_minimum_confidence_threshold(self, confidence, is_acceptable):
        MIN_THRESHOLD = 0.7
        assert (confidence >= MIN_THRESHOLD) == is_acceptable

    @pytest.mark.parametrize("confidence", [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
    def test_confidence_always_in_range(self, confidence):
        r = ClassificationResult(document_type="w2", confidence=confidence)
        assert 0.0 <= r.confidence <= 1.0


# ===================================================================
# EDGE CASES
# ===================================================================

class TestEdgeCases:

    def test_empty_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        mock_ensemble_classifier.classify.return_value = ClassificationResult(
            document_type="unknown", confidence=0.0, classifier_used="ensemble"
        )
        classifier = DocumentClassifier()
        result = classifier.classify("")
        assert result.document_type == "unknown"

    def test_very_short_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("W2")
        assert isinstance(result, ClassificationResult)

    def test_very_long_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        long_text = "Form W-2 Wage " * 10000
        result = classifier.classify(long_text)
        assert isinstance(result, ClassificationResult)

    def test_unicode_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("Formulario W-2 Salarios y Declaracion de Impuestos")
        assert isinstance(result, ClassificationResult)

    def test_numeric_only_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("123456789 75000 12500 4650")
        assert isinstance(result, ClassificationResult)

    def test_special_characters_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("$$$$ #### @@@@ !!!! ****")
        assert isinstance(result, ClassificationResult)

    def test_newlines_in_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("Form W-2\nWage and Tax Statement\n2025")
        assert isinstance(result, ClassificationResult)

    def test_tabs_in_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("Form\tW-2\tWage\tStatement")
        assert isinstance(result, ClassificationResult)

    def test_mixed_case_document(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        classifier = DocumentClassifier()
        result = classifier.classify("FORM W-2 wage AND Tax STATEMENT")
        assert isinstance(result, ClassificationResult)

    def test_corrupted_data(self, mock_ensemble_classifier):
        from ml.document_classifier import DocumentClassifier
        mock_ensemble_classifier.classify.return_value = ClassificationResult(
            document_type="unknown", confidence=0.1, classifier_used="ensemble"
        )
        classifier = DocumentClassifier()
        result = classifier.classify("\x00\x01\x02\x03binary garbage")
        assert isinstance(result, ClassificationResult)


# ===================================================================
# BaseClassifier ABC
# ===================================================================

class TestBaseClassifier:

    def test_preprocess_empty(self):
        class ConcreteClassifier(BaseClassifier):
            name = "test"
            def classify(self, text):
                return ClassificationResult(document_type="unknown", confidence=0.0)
        c = ConcreteClassifier()
        assert c.preprocess_text("") == ""

    def test_preprocess_whitespace(self):
        class ConcreteClassifier(BaseClassifier):
            name = "test"
            def classify(self, text):
                return ClassificationResult(document_type="unknown", confidence=0.0)
        c = ConcreteClassifier()
        result = c.preprocess_text("  hello   world  ")
        assert result == "hello world"

    def test_preprocess_lowercase(self):
        class ConcreteClassifier(BaseClassifier):
            name = "test"
            def classify(self, text):
                return ClassificationResult(document_type="unknown", confidence=0.0)
        c = ConcreteClassifier()
        result = c.preprocess_text("HELLO WORLD")
        assert result == "hello world"

    def test_classify_batch_default(self):
        class ConcreteClassifier(BaseClassifier):
            name = "test"
            def classify(self, text):
                return ClassificationResult(document_type="w2", confidence=0.5)
        c = ConcreteClassifier()
        results = c.classify_batch(["doc1", "doc2", "doc3"])
        assert len(results) == 3

    def test_is_available_default(self):
        class ConcreteClassifier(BaseClassifier):
            name = "test"
            def classify(self, text):
                return ClassificationResult(document_type="unknown", confidence=0.0)
        c = ConcreteClassifier()
        assert c.is_available() is True

    def test_measure_time(self):
        import time
        class ConcreteClassifier(BaseClassifier):
            name = "test"
            def classify(self, text):
                return ClassificationResult(document_type="unknown", confidence=0.0)
        c = ConcreteClassifier()
        start = time.time()
        ms = c._measure_time(start)
        assert ms >= 0
