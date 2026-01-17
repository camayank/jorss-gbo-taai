"""
Main document classifier interface.

Provides a simple, unified interface for document classification.
"""

import logging
from typing import List, Optional

from .classifiers.base import ClassificationResult, DOCUMENT_TYPES, DOCUMENT_TYPE_DESCRIPTIONS
from .classifiers.ensemble_classifier import EnsembleClassifier
from .classifiers.openai_classifier import OpenAIClassifier
from .classifiers.tfidf_classifier import TFIDFClassifier
from .classifiers.regex_classifier import RegexClassifier
from .settings import get_ml_settings, MLSettings

logger = logging.getLogger(__name__)


class DocumentClassifier:
    """
    Main document classifier for tax documents.

    Provides a simple interface for classifying tax documents using
    the configured classifier (ensemble by default).

    Usage:
        classifier = DocumentClassifier()
        result = classifier.classify("Form W-2 Wage and Tax Statement...")
        print(f"Type: {result.document_type}, Confidence: {result.confidence}")
    """

    def __init__(self, settings: Optional[MLSettings] = None):
        """
        Initialize the document classifier.

        Args:
            settings: Optional MLSettings instance. Uses default settings if None.
        """
        self.settings = settings or get_ml_settings()
        self._classifier = self._create_classifier()

    def _create_classifier(self) -> EnsembleClassifier:
        """Create the appropriate classifier based on settings."""
        return EnsembleClassifier()

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a document based on its text content.

        Args:
            text: The extracted text content of the document.

        Returns:
            ClassificationResult with document type, confidence, and metadata.
        """
        return self._classifier.classify(text)

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple documents.

        Args:
            texts: List of document text contents.

        Returns:
            List of ClassificationResult objects.
        """
        return self._classifier.classify_batch(texts)

    @staticmethod
    def get_supported_document_types() -> List[str]:
        """Get list of supported document types."""
        return [dt for dt in DOCUMENT_TYPES if dt != "unknown"]

    @staticmethod
    def get_document_type_description(document_type: str) -> str:
        """
        Get human-readable description for a document type.

        Args:
            document_type: The document type code (e.g., "w2", "1099-int").

        Returns:
            Human-readable description.
        """
        return DOCUMENT_TYPE_DESCRIPTIONS.get(document_type, "Unknown document type")

    def get_classifier_info(self) -> dict:
        """
        Get information about the classifier configuration.

        Returns:
            Dictionary with classifier information.
        """
        return {
            "primary_classifier": self.settings.primary_classifier,
            "fallback_enabled": self.settings.fallback_enabled,
            "min_confidence_threshold": self.settings.min_confidence_threshold,
            "available_classifiers": self._classifier.get_available_classifiers(),
            "openai_model": self.settings.openai_model,
        }


def create_classifier(classifier_type: str = "ensemble") -> DocumentClassifier:
    """
    Factory function to create a document classifier.

    Args:
        classifier_type: Type of classifier ("ensemble", "openai", "tfidf", "regex").

    Returns:
        Configured DocumentClassifier instance.
    """
    settings = get_ml_settings()

    # Override primary classifier based on requested type
    if classifier_type != "ensemble":
        # Create a modified settings object
        class ModifiedSettings(MLSettings):
            pass

        settings = ModifiedSettings()
        settings.primary_classifier = classifier_type
        settings.fallback_enabled = False

    return DocumentClassifier(settings=settings)
