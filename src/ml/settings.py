"""
ML Settings configuration.

Environment variable configuration for ML document classification.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """ML document classification configuration."""

    model_config = SettingsConfigDict(
        env_prefix="ML_",
        extra="ignore",
    )

    # Classifier selection
    primary_classifier: str = Field(
        default="ensemble",
        description="Primary classifier: openai, tfidf, regex, ensemble"
    )
    fallback_enabled: bool = Field(
        default=True,
        description="Enable fallback chain if primary fails"
    )

    # OpenAI settings
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model for classification"
    )
    openai_timeout: int = Field(
        default=30,
        description="Timeout for OpenAI API calls in seconds"
    )

    # Confidence thresholds
    min_confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence to accept classification"
    )
    high_confidence_threshold: float = Field(
        default=0.9,
        description="High confidence threshold for skipping fallback"
    )

    # TF-IDF model paths
    tfidf_model_path: str = Field(
        default="ml/models",
        description="Path to TF-IDF model files (relative to src/ or absolute)"
    )
    tfidf_vectorizer_file: str = Field(
        default="tfidf_vectorizer.joblib",
        description="TF-IDF vectorizer filename"
    )
    tfidf_classifier_file: str = Field(
        default="classifier_model.joblib",
        description="TF-IDF classifier filename"
    )
    tfidf_label_encoder_file: str = Field(
        default="label_encoder.joblib",
        description="Label encoder filename"
    )

    # Performance settings
    batch_size: int = Field(
        default=10,
        description="Batch size for batch classification"
    )
    cache_enabled: bool = Field(
        default=True,
        description="Enable classification result caching"
    )
    cache_ttl: int = Field(
        default=3600,
        description="Cache TTL in seconds"
    )


@lru_cache
def get_ml_settings() -> MLSettings:
    """
    Get cached ML settings instance.

    Returns:
        MLSettings: Cached settings loaded from environment.
    """
    return MLSettings()
