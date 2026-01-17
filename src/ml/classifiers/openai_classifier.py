"""
OpenAI LLM-based document classifier.

Uses OpenAI's language models to classify tax documents with high accuracy.
Provides structured JSON output with confidence scores and reasoning.
"""

import json
import os
import time
import logging
from typing import Optional, List

from openai import OpenAI

from .base import BaseClassifier, ClassificationResult, DOCUMENT_TYPES, DOCUMENT_TYPE_DESCRIPTIONS
from ..settings import get_ml_settings

logger = logging.getLogger(__name__)


class OpenAIClassifier(BaseClassifier):
    """
    OpenAI LLM-based document classifier.

    Uses GPT models to classify tax documents based on their text content.
    Provides high accuracy through zero-shot classification.
    """

    name = "openai"

    # Classification prompt template
    CLASSIFICATION_PROMPT = """You are a tax document classification expert. Analyze the following document text and classify it into one of the supported tax document types.

SUPPORTED DOCUMENT TYPES:
{document_types}

DOCUMENT TEXT:
```
{text}
```

Analyze the document and respond with a JSON object in this exact format:
{{
    "document_type": "<one of the supported types>",
    "confidence": <float between 0.0 and 1.0>,
    "reasoning": "<brief explanation of why this classification was chosen>",
    "key_indicators": ["<list of specific text patterns or phrases that led to this classification>"]
}}

IMPORTANT:
- Only use document types from the supported list above
- Set confidence based on how certain you are (1.0 = very certain, 0.5 = uncertain)
- If you cannot determine the document type, use "unknown" with low confidence
- Focus on form numbers, headers, and specific tax terminology"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the OpenAI classifier.

        Args:
            api_key: Optional OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
        """
        self.settings = get_ml_settings()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key required. Set OPENAI_API_KEY environment variable."
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        """Check if OpenAI classifier is available."""
        return bool(self.api_key)

    def _build_document_types_description(self) -> str:
        """Build formatted list of document types for the prompt."""
        lines = []
        for doc_type in DOCUMENT_TYPES:
            if doc_type != "unknown":
                desc = DOCUMENT_TYPE_DESCRIPTIONS.get(doc_type, doc_type)
                lines.append(f"- {doc_type}: {desc}")
        lines.append("- unknown: Document type cannot be determined")
        return "\n".join(lines)

    def _truncate_text(self, text: str, max_chars: int = 8000) -> str:
        """
        Truncate text to fit within token limits.

        Args:
            text: Document text.
            max_chars: Maximum characters to include.

        Returns:
            Truncated text.
        """
        if len(text) <= max_chars:
            return text

        # Take beginning and end portions
        half = max_chars // 2
        return text[:half] + "\n...[truncated]...\n" + text[-half:]

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify document using OpenAI LLM.

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

        if not self.is_available():
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"reason": "api_key_not_configured"},
            )

        # Preprocess and truncate text
        processed_text = self.preprocess_text(text)
        truncated_text = self._truncate_text(processed_text)

        # Build the prompt
        prompt = self.CLASSIFICATION_PROMPT.format(
            document_types=self._build_document_types_description(),
            text=truncated_text,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a tax document classification expert. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=500,
                response_format={"type": "json_object"},
                timeout=self.settings.openai_timeout,
            )

            # Parse response
            response_text = response.choices[0].message.content
            result = json.loads(response_text)

            document_type = result.get("document_type", "unknown").lower()
            confidence = float(result.get("confidence", 0.5))

            # Validate document type
            if document_type not in DOCUMENT_TYPES:
                document_type = "unknown"
                confidence = min(confidence, 0.5)

            # Build probabilities (OpenAI doesn't provide full distribution)
            probabilities = {dt: 0.0 for dt in DOCUMENT_TYPES}
            probabilities[document_type] = confidence
            probabilities["unknown"] = 1.0 - confidence

            return ClassificationResult(
                document_type=document_type,
                confidence=confidence,
                probabilities=probabilities,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={
                    "reasoning": result.get("reasoning", ""),
                    "key_indicators": result.get("key_indicators", []),
                    "model": self.settings.openai_model,
                    "tokens_used": response.usage.total_tokens if response.usage else 0,
                },
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI response: {e}")
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"error": f"json_parse_error: {str(e)}"},
            )
        except Exception as e:
            logger.error(f"OpenAI classification failed: {e}")
            return ClassificationResult(
                document_type="unknown",
                confidence=0.0,
                classifier_used=self.name,
                processing_time_ms=self._measure_time(start_time),
                metadata={"error": str(e)},
            )

    def classify_batch(self, texts: List[str]) -> List[ClassificationResult]:
        """
        Classify multiple documents.

        For OpenAI, we process sequentially to manage rate limits.
        Could be optimized with async/await for parallel processing.

        Args:
            texts: List of document text contents.

        Returns:
            List of ClassificationResult objects.
        """
        results = []
        for text in texts:
            result = self.classify(text)
            results.append(result)
        return results
