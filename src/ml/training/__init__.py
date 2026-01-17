"""
Training module for ML document classifiers.

Contains utilities for generating synthetic training data
and training the TF-IDF classifier.
"""

from .synthetic_data_generator import SyntheticDataGenerator
from .trainer import DocumentClassifierTrainer

__all__ = [
    "SyntheticDataGenerator",
    "DocumentClassifierTrainer",
]
