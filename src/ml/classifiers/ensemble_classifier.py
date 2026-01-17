"""
Ensemble document classifier.

Combines multiple classifiers with fallback chain for robust classification.
"""

import logging
import time
from typing import List, Optional, Dict, Any

from .base import BaseClassifier, ClassificationResult, DOCUMENT_TYPES
from .openai_classifier import OpenAIClassifier
from .tfidf_classifier import TFIDFClassifier
from .regex_classifier import RegexClassifier
from ..settings import get_ml_settings

logger = logging.getLogger(__name__)


class EnsembleClassifier(BaseClassifier):
    """
    Ensemble classifier with fallback chain.

    Classification cascade:
    1. Try primary classifier (OpenAI by default)
    2. If confidence < threshold, try secondary (TF-IDF)
    3. If still low confidence, fall back to regex
    4. Return best result based on confidence
    """

    name = "ensemble"

    def __init__(
        self,
        openai_classifier: Optional[OpenAIClassifier] = None,
        tfidf_classifier: Optional[TFIDFClassifier] = None,
        regex_classifier: Optional[RegexClassifier] = None,
    ):
        """
        Initialize the ensemble classifier.

        Args:
            openai_classifier: OpenAI classifier instance (created if None).
            tfidf_classifier: TF-IDF classifier instance (created if None).
            regex_classifier: Regex classifier instance (created if None).
        """
        self.settings = get_ml_settings()

        # Initialize classifiers
        self.openai_classifier = openai_classifier or OpenAIClassifier()
        self.tfidf_classifier = tfidf_classifier or TFIDFClassifier()
        self.regex_classifier = regex_classifier or RegexClassifier()

        # Build classifier chain based on settings
        self._build_classifier_chain()

    def _build_classifier_chain(self) -> None:
        """Build the classifier chain based on settings."""
        self.classifiers: List[BaseClassifier] = []

        primary = self.settings.primary_classifier.lower()

        if primary == "openai":
            if self.openai_classifier.is_available():
                self.classifiers.append(self.openai_classifier)
        elif primary == "tfidf":
            if self.tfidf_classifier.is_available():
                self.classifiers.append(self.tfidf_classifier)
        elif primary == "regex":
            self.classifiers.append(self.regex_classifier)
        elif primary == "ensemble":
            # Full ensemble: OpenAI -> TF-IDF -> Regex
            if self.openai_classifier.is_available():
                self.classifiers.append(self.openai_classifier)
            if self.tfidf_classifier.is_available():
                self.classifiers.append(self.tfidf_classifier)
            self.classifiers.append(self.regex_classifier)

        # Add fallbacks if enabled
        if self.settings.fallback_enabled and primary != "ensemble":
            if self.tfidf_classifier.is_available() and self.tfidf_classifier not in self.classifiers:
                self.classifiers.append(self.tfidf_classifier)
            if self.regex_classifier not in self.classifiers:
                self.classifiers.append(self.regex_classifier)

        # Always ensure regex as final fallback
        if not self.classifiers or self.regex_classifier not in self.classifiers:
            self.classifiers.append(self.regex_classifier)

        logger.info(f"Ensemble classifier chain: {[c.name for c in self.classifiers]}")

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify document using the ensemble approach.

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

        results: List[ClassificationResult] = []
        best_result: Optional[ClassificationResult] = None

        for classifier in self.classifiers:
            try:
                result = classifier.classify(text)
                results.append(result)

                # Track best result so far
                if best_result is None or result.confidence > best_result.confidence:
                    best_result = result

                # If high confidence, no need to try more classifiers
                if result.confidence >= self.settings.high_confidence_threshold:
                    logger.debug(
                        f"High confidence ({result.confidence:.2f}) from {classifier.name}, "
                        "skipping remaining classifiers"
                    )
                    break

                # If confidence is acceptable and we have limited classifiers left
                if result.confidence >= self.settings.min_confidence_threshold:
                    logger.debug(
                        f"Acceptable confidence ({result.confidence:.2f}) from {classifier.name}"
                    )
                    # Continue to potentially find better result

            except Exception as e:
                logger.warning(f"Classifier {classifier.name} failed: {e}")
                continue

        if best_result is None:
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"reason": "all_classifiers_failed"},
            )

        # Aggregate results using weighted voting if multiple classifiers succeeded
        final_result = self._aggregate_results(results, best_result)
        final_result.processing_time_ms = self._measure_time(start_time)

        return final_result

    def _aggregate_results(
        self,
        results: List[ClassificationResult],
        best_result: ClassificationResult,
    ) -> ClassificationResult:
        """
        Aggregate results from multiple classifiers.

        Uses weighted voting based on confidence scores.

        Args:
            results: List of classification results.
            best_result: The result with highest confidence.

        Returns:
            Aggregated ClassificationResult.
        """
        if len(results) == 1:
            # Only one result, use it directly
            result = results[0]
            return ClassificationResult(
                document_type=result.document_type,
                confidence=result.confidence,
                probabilities=result.probabilities,
                classifier_used=f"{self.name}({result.classifier_used})",
                metadata={
                    "classifiers_used": [result.classifier_used],
                    "all_results": [r.to_dict() for r in results],
                },
            )

        # Multiple results - use weighted voting
        votes: Dict[str, float] = {dt: 0.0 for dt in DOCUMENT_TYPES}
        total_weight = 0.0

        classifier_weights = {
            "openai": 1.0,      # Highest weight for LLM
            "tfidf": 0.7,       # Medium weight for ML
            "regex": 0.5,       # Lower weight for regex
        }

        for result in results:
            weight = classifier_weights.get(result.classifier_used, 0.5)
            weighted_confidence = result.confidence * weight
            votes[result.document_type] += weighted_confidence
            total_weight += weight

        # Normalize votes
        if total_weight > 0:
            votes = {k: v / total_weight for k, v in votes.items()}

        # Find winner
        winner = max(votes.keys(), key=lambda k: votes[k])
        confidence = votes[winner]

        # Build probability distribution
        total_votes = sum(votes.values())
        if total_votes > 0:
            probabilities = {k: v / total_votes for k, v in votes.items()}
        else:
            probabilities = votes

        return ClassificationResult(
            document_type=winner,
            confidence=confidence,
            probabilities=probabilities,
            classifier_used=self.name,
            metadata={
                "voting_method": "weighted",
                "classifiers_used": [r.classifier_used for r in results],
                "votes": votes,
                "all_results": [r.to_dict() for r in results],
            },
        )

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple documents.

        Args:
            texts: List of document text contents.

        Returns:
            List of ClassificationResult objects.
        """
        return [self.classify(text) for text in texts]

    def get_available_classifiers(self) -> List[str]:
        """Get list of available classifier names in the chain."""
        return [c.name for c in self.classifiers]
