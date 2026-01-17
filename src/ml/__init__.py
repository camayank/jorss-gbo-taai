"""
ML-based document classification module.

Provides high-accuracy document classification for tax documents
using a hybrid approach: OpenAI LLM, TF-IDF ML, and regex fallback.
"""

from .document_classifier import DocumentClassifier
from .settings import MLSettings, get_ml_settings
from .classifiers.base import ClassificationResult, BaseClassifier

__all__ = [
    "DocumentClassifier",
    "MLSettings",
    "get_ml_settings",
    "ClassificationResult",
    "BaseClassifier",
]
