"""
TF-IDF based document classifier.

Uses traditional ML (TF-IDF + LogisticRegression) for fast, offline classification.
Can be trained on synthetic or real data and improves over time.
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np

from .base import BaseClassifier, ClassificationResult, DOCUMENT_TYPES
from ..settings import get_ml_settings

logger = logging.getLogger(__name__)

# Lazy import sklearn to avoid startup overhead if not used
_sklearn_available = None


def _check_sklearn() -> bool:
    """Check if sklearn is available."""
    global _sklearn_available
    if _sklearn_available is None:
        try:
            import sklearn  # noqa: F401
            import joblib  # noqa: F401
            _sklearn_available = True
        except ImportError:
            _sklearn_available = False
    return _sklearn_available


class TFIDFClassifier(BaseClassifier):
    """
    TF-IDF based document classifier.

    Uses TfidfVectorizer + LogisticRegression for fast classification.
    Models are loaded from disk and can be updated through retraining.
    """

    name = "tfidf"

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the TF-IDF classifier.

        Args:
            model_path: Path to directory containing trained model files.
                       If not provided, uses path from settings.
        """
        self.settings = get_ml_settings()
        self.model_path = Path(model_path or self.settings.tfidf_model_path)

        self._vectorizer = None
        self._classifier = None
        self._label_encoder = None
        self._loaded = False

    def _load_models(self) -> bool:
        """
        Load trained models from disk.

        Returns:
            True if models loaded successfully, False otherwise.
        """
        if self._loaded:
            return True

        if not _check_sklearn():
            logger.warning("sklearn not available, TF-IDF classifier disabled")
            return False

        import joblib

        vectorizer_path = self.model_path / self.settings.tfidf_vectorizer_file
        classifier_path = self.model_path / self.settings.tfidf_classifier_file
        encoder_path = self.model_path / self.settings.tfidf_label_encoder_file

        if not all(p.exists() for p in [vectorizer_path, classifier_path, encoder_path]):
            logger.warning(f"TF-IDF model files not found in {self.model_path}")
            return False

        try:
            self._vectorizer = joblib.load(vectorizer_path)
            self._classifier = joblib.load(classifier_path)
            self._label_encoder = joblib.load(encoder_path)
            self._loaded = True
            logger.info("TF-IDF models loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load TF-IDF models: {e}")
            return False

    def is_available(self) -> bool:
        """Check if TF-IDF classifier is available."""
        if not _check_sklearn():
            return False
        return self._load_models()

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify document using TF-IDF + LogisticRegression.

        Args:
            text: The extracted text content of the document.

        Returns:
            ClassificationResult with document type and confidence.
        """
        start_time = time.time()

        if not text:
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"reason": "empty_text"},
            )

        if not self._load_models():
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"reason": "models_not_loaded"},
            )

        try:
            # Preprocess text
            processed_text = self.preprocess_text(text)

            # Transform text to TF-IDF features
            features = self._vectorizer.transform([processed_text])

            # Get prediction probabilities
            proba = self._classifier.predict_proba(features)[0]

            # Get class labels
            classes = self._label_encoder.classes_

            # Find best class
            best_idx = np.argmax(proba)
            document_type = classes[best_idx]
            confidence = float(proba[best_idx])

            # Build full probability distribution
            probabilities = {dt: 0.0 for dt in DOCUMENT_TYPES}
            for i, cls in enumerate(classes):
                if cls in probabilities:
                    probabilities[cls] = float(proba[i])

            # Ensure probabilities sum to 1
            total = sum(probabilities.values())
            if total > 0:
                probabilities = {k: v / total for k, v in probabilities.items()}

            return ClassificationResult(
                document_type=document_type,
                confidence=confidence,
                probabilities=probabilities,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={
                    "top_3": self._get_top_predictions(classes, proba, 3),
                },
            )

        except Exception as e:
            logger.error(f"TF-IDF classification failed: {e}")
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"error": str(e)},
            )

    def _get_top_predictions(
        self, classes: np.ndarray, proba: np.ndarray, n: int
    ) -> List[Tuple[str, float]]:
        """Get top N predictions with probabilities."""
        indices = np.argsort(proba)[::-1][:n]
        return [(classes[i], float(proba[i])) for i in indices]

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple documents efficiently.

        Uses batch transformation for better performance.

        Args:
            texts: List of document text contents.

        Returns:
            List of ClassificationResult objects.
        """
        start_time = time.time()

        if not self._load_models():
            return [
                ClassificationResult(
                    document_type="unknown",
                    confidence=0.0,
                    classifier_used=self.name,
                    metadata={"reason": "models_not_loaded"},
                )
                for _ in texts
            ]

        try:
            # Preprocess all texts
            processed_texts = [self.preprocess_text(t) for t in texts]

            # Batch transform
            features = self._vectorizer.transform(processed_texts)

            # Batch predict
            probas = self._classifier.predict_proba(features)

            # Get class labels
            classes = self._label_encoder.classes_

            results = []
            for i, proba in enumerate(probas):
                best_idx = np.argmax(proba)
                document_type = classes[best_idx]
                confidence = float(proba[best_idx])

                probabilities = {dt: 0.0 for dt in DOCUMENT_TYPES}
                for j, cls in enumerate(classes):
                    if cls in probabilities:
                        probabilities[cls] = float(proba[j])

                results.append(
                    ClassificationResult(
                        document_type=document_type,
                        confidence=confidence,
                        probabilities=probabilities,
                        classifier_used=self.name,
                        processing_time_ms=self._measure_time(start_time) // len(texts),
                        metadata={
                            "top_3": self._get_top_predictions(classes, proba, 3),
                        },
                    )
                )

            return results

        except Exception as e:
            logger.error(f"TF-IDF batch classification failed: {e}")
            return [
                ClassificationResult(
                    document_type="unknown",
                    confidence=0.0,
                    classifier_used=self.name,
                    metadata={"error": str(e)},
                )
                for _ in texts
            ]
