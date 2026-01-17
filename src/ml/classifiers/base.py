"""
Base classifier interface and result dataclass.

Defines the common interface for all document classifiers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import re
import time


# Supported document types for tax document classification
DOCUMENT_TYPES = [
    "w2",
    "w2g",
    "1099-int",
    "1099-div",
    "1099-nec",
    "1099-misc",
    "1099-b",
    "1099-r",
    "1099-g",
    "1099-k",
    "1099-sa",
    "1099-q",
    "1099-c",
    "1099-s",
    "1099-oid",
    "1099-ltc",
    "1099-patr",
    "1098",
    "1098-e",
    "1098-t",
    "k1",
    "1095-a",
    "1095-b",
    "1095-c",
    "ssa-1099",
    "rrb-1099",
    "5498",
    "5498-sa",
    "unknown",
]

DOCUMENT_TYPE_DESCRIPTIONS = {
    "w2": "W-2: Wage and Tax Statement",
    "w2g": "W-2G: Gambling Winnings",
    "1099-int": "1099-INT: Interest Income",
    "1099-div": "1099-DIV: Dividends and Distributions",
    "1099-nec": "1099-NEC: Nonemployee Compensation",
    "1099-misc": "1099-MISC: Miscellaneous Income",
    "1099-b": "1099-B: Broker Transactions",
    "1099-r": "1099-R: Retirement Distributions",
    "1099-g": "1099-G: Government Payments",
    "1099-k": "1099-K: Payment Card and Third Party Network Transactions",
    "1099-sa": "1099-SA: Distributions from HSA, Archer MSA, or Medicare Advantage MSA",
    "1099-q": "1099-Q: Payments from Qualified Education Programs (529 Plans)",
    "1099-c": "1099-C: Cancellation of Debt",
    "1099-s": "1099-S: Proceeds from Real Estate Transactions",
    "1099-oid": "1099-OID: Original Issue Discount",
    "1099-ltc": "1099-LTC: Long-Term Care and Accelerated Death Benefits",
    "1099-patr": "1099-PATR: Taxable Distributions from Cooperatives",
    "1098": "1098: Mortgage Interest Statement",
    "1098-e": "1098-E: Student Loan Interest Statement",
    "1098-t": "1098-T: Tuition Statement",
    "k1": "Schedule K-1: Partner/Shareholder Income",
    "1095-a": "1095-A: Health Insurance Marketplace Statement",
    "1095-b": "1095-B: Health Coverage",
    "1095-c": "1095-C: Employer-Provided Health Insurance Offer and Coverage",
    "ssa-1099": "SSA-1099: Social Security Benefit Statement",
    "rrb-1099": "RRB-1099: Railroad Retirement Benefits",
    "5498": "5498: IRA Contribution Information",
    "5498-sa": "5498-SA: HSA, Archer MSA, or Medicare Advantage MSA Information",
    "unknown": "Unknown document type",
}


@dataclass
class ClassificationResult:
    """Result of document classification."""

    document_type: str
    confidence: float  # 0.0 - 1.0
    probabilities: Dict[str, float] = field(default_factory=dict)
    classifier_used: str = ""
    processing_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize the result."""
        # Ensure document type is valid
        if self.document_type not in DOCUMENT_TYPES:
            self.document_type = "unknown"

        # Clamp confidence to [0, 1]
        self.confidence = max(0.0, min(1.0, self.confidence))

        # Ensure probabilities sum to ~1.0 if provided
        if self.probabilities:
            total = sum(self.probabilities.values())
            if total > 0 and abs(total - 1.0) > 0.01:
                self.probabilities = {
                    k: v / total for k, v in self.probabilities.items()
                }

    @property
    def confidence_percent(self) -> float:
        """Return confidence as percentage (0-100)."""
        return self.confidence * 100

    @property
    def document_type_description(self) -> str:
        """Return human-readable document type description."""
        return DOCUMENT_TYPE_DESCRIPTIONS.get(
            self.document_type, "Unknown document type"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "document_type": self.document_type,
            "confidence": self.confidence,
            "confidence_percent": self.confidence_percent,
            "probabilities": self.probabilities,
            "classifier_used": self.classifier_used,
            "processing_time_ms": self.processing_time_ms,
            "metadata": self.metadata,
        }


class BaseClassifier(ABC):
    """
    Abstract base class for document classifiers.

    All classifier implementations should inherit from this class
    and implement the classify() method.
    """

    name: str = "base"

    @abstractmethod
    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a document based on its text content.

        Args:
            text: The extracted text content of the document.

        Returns:
            ClassificationResult with document type and confidence.
        """
        pass

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple documents.

        Default implementation calls classify() for each text.
        Subclasses may override for more efficient batch processing.

        Args:
            texts: List of document text contents.

        Returns:
            List of ClassificationResult objects.
        """
        return [self.classify(text) for text in texts]

    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for classification.

        Normalizes whitespace, converts to lowercase, and removes
        special characters that don't contribute to classification.

        Args:
            text: Raw document text.

        Returns:
            Preprocessed text.
        """
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove special characters but keep alphanumeric, spaces, and basic punctuation
        text = re.sub(r'[^\w\s\-\.\,\$\%]', '', text)

        return text.strip()

    def _measure_time(self, start_time: float) -> int:
        """
        Calculate elapsed time in milliseconds.

        Args:
            start_time: Start time from time.time().

        Returns:
            Elapsed time in milliseconds.
        """
        return int((time.time() - start_time) * 1000)

    def is_available(self) -> bool:
        """
        Check if the classifier is available for use.

        Returns:
            True if the classifier can be used, False otherwise.
        """
        return True
