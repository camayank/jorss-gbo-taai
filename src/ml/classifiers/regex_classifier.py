"""
Regex-based document classifier.

Wrapper around the existing regex classification logic from DocumentProcessor.
Provides a fast, reliable fallback when ML classifiers are unavailable.
"""

import re
import time
from typing import Dict, List

from .base import BaseClassifier, ClassificationResult, DOCUMENT_TYPES


class RegexClassifier(BaseClassifier):
    """
    Regex-based document classifier.

    Uses pattern matching to identify tax document types based on
    known indicators and form identifiers.
    """

    name = "regex"

    # Document type indicators (patterns for each form type)
    DOCUMENT_INDICATORS: Dict[str, List[str]] = {
        "w2": [
            r"form\s*w-?2",
            r"wage\s+and\s+tax\s+statement",
            r"employer.s?\s+identification\s+number",
            r"box\s*1.*wages.*tips",
            r"social\s+security\s+wages",
            r"medicare\s+wages",
        ],
        "1099-int": [
            r"form\s*1099-?int",
            r"interest\s+income",
            r"early\s+withdrawal\s+penalty",
            r"tax.exempt\s+interest",
        ],
        "1099-div": [
            r"form\s*1099-?div",
            r"dividends\s+and\s+distributions",
            r"ordinary\s+dividends",
            r"qualified\s+dividends",
            r"capital\s+gain\s+(?:distr|dist)",
        ],
        "1099-nec": [
            r"form\s*1099-?nec",
            r"nonemployee\s+compensation",
        ],
        "1099-misc": [
            r"form\s*1099-?misc",
            r"miscellaneous\s+(?:income|information)",
            r"rents.*royalties",
        ],
        "1099-b": [
            r"form\s*1099-?b",
            r"proceeds\s+from\s+broker",
            r"barter\s+exchange",
            r"cost\s+or\s+other\s+basis",
        ],
        "1099-r": [
            r"form\s*1099-?r",
            r"distributions\s+from\s+pensions",
            r"annuities.*retirement",
            r"ira.*distribution",
        ],
        "1099-g": [
            r"form\s*1099-?g",
            r"government\s+payments",
            r"unemployment\s+compensation",
            r"state.*local\s+income\s+tax\s+refunds",
        ],
        "1098": [
            r"form\s*1098\b",
            r"mortgage\s+interest\s+statement",
            r"mortgage\s+interest\s+received",
        ],
        "1098-e": [
            r"form\s*1098-?e",
            r"student\s+loan\s+interest",
        ],
        "1098-t": [
            r"form\s*1098-?t",
            r"tuition\s+statement",
            r"payments\s+received.*qualified\s+tuition",
        ],
        "k1": [
            r"schedule\s*k-?1",
            r"partner.s?\s+share",
            r"shareholder.s?\s+share",
            r"beneficiary.s?\s+share",
        ],
        "1095-a": [
            r"form\s*1095-?a",
            r"health\s+insurance\s+marketplace",
            r"premium\s+tax\s+credit",
        ],
        "1095-b": [
            r"form\s*1095-?b",
            r"health\s+coverage",
            r"minimum\s+essential\s+coverage",
        ],
        "1095-c": [
            r"form\s*1095-?c",
            r"employer.provided\s+health\s+insurance",
            r"offer\s+and\s+coverage",
        ],
    }

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify document using regex pattern matching.

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

        text_lower = text.lower()
        scores: Dict[str, Dict] = {}

        for doc_type, patterns in self.DOCUMENT_INDICATORS.items():
            score = 0
            matched_patterns = []

            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
                    matched_patterns.append(pattern)

            if score > 0:
                # Normalize score (percentage of patterns matched)
                confidence = score / len(patterns)
                scores[doc_type] = {
                    "confidence": confidence,
                    "matched_patterns": matched_patterns,
                    "total_patterns": len(patterns),
                }

        if not scores:
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"reason": "no_patterns_matched"},
            )

        # Get highest scoring document type
        best_type = max(scores.keys(), key=lambda k: scores[k]["confidence"])
        best_score = scores[best_type]

        # Calculate probabilities for all document types
        probabilities = {doc_type: 0.0 for doc_type in DOCUMENT_TYPES}
        total_confidence = sum(s["confidence"] for s in scores.values())

        if total_confidence > 0:
            for doc_type, score_info in scores.items():
                probabilities[doc_type] = score_info["confidence"] / total_confidence

        # Set unknown probability as complement
        probabilities["unknown"] = max(0.0, 1.0 - sum(
            p for k, p in probabilities.items() if k != "unknown"
        ))

        return ClassificationResult(
            document_type=best_type,
            confidence=best_score["confidence"],
            probabilities=probabilities,
            classifier_used=self.name,
            processing_time_ms=self._measure_time(start_time),
            metadata={
                "matched_patterns": best_score["matched_patterns"],
                "total_patterns": best_score["total_patterns"],
                "all_scores": {k: v["confidence"] for k, v in scores.items()},
            },
        )

    def get_supported_types(self) -> List[str]:
        """Get list of document types this classifier can identify."""
        return list(self.DOCUMENT_INDICATORS.keys())
