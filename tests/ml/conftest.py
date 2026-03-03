"""
Fixtures for ML document classifier tests.
Provides sample document texts and classifier mocks.
"""
import os
import sys
from pathlib import Path

import pytest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


# ---------------------------------------------------------------------------
# Sample document texts by type
# ---------------------------------------------------------------------------

SAMPLE_DOCUMENTS = {
    "w2": (
        "Form W-2 Wage and Tax Statement 2025. "
        "Employee's social security number 123-45-6789. "
        "Employer identification number 98-7654321. "
        "Wages, tips, other compensation $75,000.00. "
        "Federal income tax withheld $12,500.00. "
        "Social security wages $75,000.00. "
        "Social security tax withheld $4,650.00. "
        "Medicare wages and tips $75,000.00. "
        "Employer's name: Acme Corporation."
    ),
    "1099-int": (
        "Form 1099-INT Interest Income 2025. "
        "Payer's name: First National Bank. "
        "Payer's TIN: 12-3456789. "
        "Recipient's TIN: 987-65-4321. "
        "Interest income $1,250.00. "
        "Early withdrawal penalty $0.00. "
        "Interest on U.S. Savings Bonds $0.00. "
        "Federal income tax withheld $0.00."
    ),
    "1099-div": (
        "Form 1099-DIV Dividends and Distributions 2025. "
        "Payer's name: Vanguard Total Stock Market. "
        "Total ordinary dividends $3,200.00. "
        "Qualified dividends $2,800.00. "
        "Total capital gain distributions $500.00. "
        "Federal income tax withheld $0.00."
    ),
    "1099-misc": (
        "Form 1099-MISC Miscellaneous Income 2025. "
        "Payer's name: Consulting Client LLC. "
        "Rents $0. Royalties $0. "
        "Other income $5,000.00. "
        "Federal income tax withheld $0."
    ),
    "1099-nec": (
        "Form 1099-NEC Nonemployee Compensation 2025. "
        "Payer's name: Tech Startup Inc. "
        "Nonemployee compensation $45,000.00. "
        "Payer's TIN: 55-1234567. "
        "Federal income tax withheld $0."
    ),
    "1099-k": (
        "Form 1099-K Payment Card and Third Party Network Transactions 2025. "
        "Filer's name: PayPal Inc. "
        "Gross amount of payment card/third party network transactions $25,000.00. "
        "Number of payment transactions: 150."
    ),
    "1098": (
        "Form 1098 Mortgage Interest Statement 2025. "
        "Recipient/Lender: Wells Fargo Home Mortgage. "
        "Mortgage interest received $12,500.00. "
        "Outstanding mortgage principal $350,000.00. "
        "Points paid on purchase of principal residence $0."
    ),
    "k1": (
        "Schedule K-1 (Form 1065) Partner's Share of Income 2025. "
        "Partnership's name: Real Estate Partners LP. "
        "Partner's share of profit 25%. "
        "Ordinary business income (loss) $15,000. "
        "Net rental real estate income $8,000. "
        "Guaranteed payments $0."
    ),
    "1040": (
        "Form 1040 U.S. Individual Income Tax Return 2025. "
        "Filing status: Single. "
        "Total income $95,000. "
        "Adjusted gross income $85,000. "
        "Taxable income $70,000. "
        "Tax $11,000. "
        "Total payments $14,000. "
        "Amount overpaid $3,000."
    ),
}


@pytest.fixture
def sample_w2_text():
    return SAMPLE_DOCUMENTS["w2"]


@pytest.fixture
def sample_1099_int_text():
    return SAMPLE_DOCUMENTS["1099-int"]


@pytest.fixture
def sample_1099_div_text():
    return SAMPLE_DOCUMENTS["1099-div"]


@pytest.fixture
def sample_1099_misc_text():
    return SAMPLE_DOCUMENTS["1099-misc"]


@pytest.fixture
def sample_1099_nec_text():
    return SAMPLE_DOCUMENTS["1099-nec"]


@pytest.fixture
def sample_1099_k_text():
    return SAMPLE_DOCUMENTS["1099-k"]


@pytest.fixture
def sample_1098_text():
    return SAMPLE_DOCUMENTS["1098"]


@pytest.fixture
def sample_k1_text():
    return SAMPLE_DOCUMENTS["k1"]


@pytest.fixture
def sample_1040_text():
    return SAMPLE_DOCUMENTS["1040"]


@pytest.fixture
def all_sample_documents():
    return SAMPLE_DOCUMENTS


@pytest.fixture
def empty_document():
    return ""


@pytest.fixture
def garbage_document():
    return "asdfghjkl qwertyuiop zxcvbnm 12345 !@#$%"


@pytest.fixture
def mock_classifier():
    """Create a mock classifier that returns configurable results."""
    from ml.classifiers.base import ClassificationResult

    classifier = Mock()
    classifier.classify.return_value = ClassificationResult(
        document_type="w2",
        confidence=0.95,
        classifier_used="mock",
    )
    classifier.classify_batch.return_value = [
        ClassificationResult(document_type="w2", confidence=0.95, classifier_used="mock"),
    ]
    return classifier


@pytest.fixture
def mock_ensemble_classifier():
    """Mock the EnsembleClassifier."""
    with patch("ml.document_classifier.EnsembleClassifier") as MockEnsemble:
        from ml.classifiers.base import ClassificationResult
        instance = MockEnsemble.return_value
        instance.classify.return_value = ClassificationResult(
            document_type="w2", confidence=0.95, classifier_used="ensemble"
        )
        instance.classify_batch.side_effect = lambda texts: [
            ClassificationResult(document_type="w2", confidence=0.90, classifier_used="ensemble")
            for _ in texts
        ]
        instance.get_available_classifiers.return_value = ["regex", "tfidf"]
        yield instance


@pytest.fixture
def mock_ml_settings():
    """Mock ML settings."""
    settings = Mock()
    settings.primary_classifier = "ensemble"
    settings.fallback_enabled = True
    settings.min_confidence_threshold = 0.7
    settings.high_confidence_threshold = 0.9
    return settings
