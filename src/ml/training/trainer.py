"""
Document classifier trainer.

Trains and saves TF-IDF based document classifier models.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from .synthetic_data_generator import SyntheticDataGenerator

logger = logging.getLogger(__name__)

# Lazy import sklearn
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


class DocumentClassifierTrainer:
    """
    Trainer for TF-IDF document classifier.

    Handles training, evaluation, and saving of document classification models.
    """

    def __init__(
        self,
        model_path: str = "src/ml/models",
        vectorizer_file: str = "tfidf_vectorizer.joblib",
        classifier_file: str = "classifier_model.joblib",
        encoder_file: str = "label_encoder.joblib",
    ):
        """
        Initialize the trainer.

        Args:
            model_path: Directory to save trained models.
            vectorizer_file: Filename for TF-IDF vectorizer.
            classifier_file: Filename for classifier model.
            encoder_file: Filename for label encoder.
        """
        self.model_path = Path(model_path)
        self.vectorizer_file = vectorizer_file
        self.classifier_file = classifier_file
        self.encoder_file = encoder_file

        self.vectorizer = None
        self.classifier = None
        self.label_encoder = None

    def train(
        self,
        texts: List[str],
        labels: List[str],
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Dict[str, Any]:
        """
        Train the classifier on provided data.

        Args:
            texts: List of document texts.
            labels: List of document type labels.
            test_size: Fraction of data to use for testing.
            random_state: Random seed for reproducibility.

        Returns:
            Dictionary with training metrics.
        """
        if not _check_sklearn():
            raise ImportError(
                "scikit-learn is required for training. "
                "Install with: pip install scikit-learn joblib"
            )

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import LabelEncoder
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report, accuracy_score

        logger.info(f"Training on {len(texts)} samples...")

        # Encode labels
        self.label_encoder = LabelEncoder()
        encoded_labels = self.label_encoder.fit_transform(labels)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            texts, encoded_labels, test_size=test_size, random_state=random_state, stratify=encoded_labels
        )

        logger.info(f"Train set: {len(X_train)}, Test set: {len(X_test)}")

        # Create and fit vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            lowercase=True,
            strip_accents="unicode",
        )

        X_train_tfidf = self.vectorizer.fit_transform(X_train)
        X_test_tfidf = self.vectorizer.transform(X_test)

        logger.info(f"Vocabulary size: {len(self.vectorizer.vocabulary_)}")

        # Train classifier
        self.classifier = LogisticRegression(
            max_iter=1000,
            solver="lbfgs",
            class_weight="balanced",
            random_state=random_state,
        )

        self.classifier.fit(X_train_tfidf, y_train)

        # Evaluate
        y_pred = self.classifier.predict(X_test_tfidf)
        accuracy = accuracy_score(y_test, y_pred)

        # Get classification report
        report = classification_report(
            y_test,
            y_pred,
            target_names=self.label_encoder.classes_,
            output_dict=True,
        )

        logger.info(f"Test accuracy: {accuracy:.4f}")

        return {
            "accuracy": accuracy,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "vocabulary_size": len(self.vectorizer.vocabulary_),
            "classes": list(self.label_encoder.classes_),
            "classification_report": report,
        }

    def train_on_synthetic_data(
        self,
        samples_per_type: int = 200,
        document_types: List[str] = None,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Train classifier using synthetic data.

        Args:
            samples_per_type: Number of synthetic samples per document type.
            document_types: Document types to include. None for all.
            seed: Random seed for data generation.

        Returns:
            Dictionary with training metrics.
        """
        logger.info("Generating synthetic training data...")

        generator = SyntheticDataGenerator(seed=seed)
        texts, labels = generator.generate_dataset(
            samples_per_type=samples_per_type,
            document_types=document_types,
        )

        logger.info(f"Generated {len(texts)} synthetic documents")

        return self.train(texts, labels, random_state=seed)

    def save_models(self) -> None:
        """Save trained models to disk."""
        if not _check_sklearn():
            raise ImportError("scikit-learn is required for saving models.")

        import joblib

        if self.vectorizer is None or self.classifier is None or self.label_encoder is None:
            raise ValueError("Models not trained. Call train() first.")

        # Ensure directory exists
        self.model_path.mkdir(parents=True, exist_ok=True)

        # Save models
        joblib.dump(self.vectorizer, self.model_path / self.vectorizer_file)
        joblib.dump(self.classifier, self.model_path / self.classifier_file)
        joblib.dump(self.label_encoder, self.model_path / self.encoder_file)

        logger.info(f"Models saved to {self.model_path}")

    def load_models(self) -> bool:
        """
        Load trained models from disk.

        Returns:
            True if loaded successfully, False otherwise.
        """
        if not _check_sklearn():
            return False

        import joblib

        vectorizer_path = self.model_path / self.vectorizer_file
        classifier_path = self.model_path / self.classifier_file
        encoder_path = self.model_path / self.encoder_file

        if not all(p.exists() for p in [vectorizer_path, classifier_path, encoder_path]):
            return False

        try:
            self.vectorizer = joblib.load(vectorizer_path)
            self.classifier = joblib.load(classifier_path)
            self.label_encoder = joblib.load(encoder_path)
            return True
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            return False


def train_and_save_models(
    model_path: str = "ml/models",
    samples_per_type: int = 200,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Convenience function to train and save models.

    Args:
        model_path: Directory to save models.
        samples_per_type: Number of synthetic samples per document type.
        seed: Random seed.

    Returns:
        Training metrics.
    """
    trainer = DocumentClassifierTrainer(model_path=model_path)
    metrics = trainer.train_on_synthetic_data(
        samples_per_type=samples_per_type,
        seed=seed,
    )
    trainer.save_models()
    return metrics


if __name__ == "__main__":
    # Train and save models when run directly
    logging.basicConfig(level=logging.INFO)
    metrics = train_and_save_models()
    print(f"\nTraining complete. Accuracy: {metrics['accuracy']:.4f}")
